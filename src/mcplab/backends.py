"""HTTP model backends for the agent loop (needs the ``agent`` extra: httpx).

One ``HttpAgent`` drives the MCP Browser tool loop against four provider shapes:

* ``openai`` - OpenAI-compatible chat completions (also vLLM, LM Studio);
* ``ollama`` - a local Ollama server's OpenAI-compatible endpoint;
* ``anthropic`` - the Anthropic Messages API;
* ``gemini`` - Google Gemini ``generateContent``.

Keys are read from the environment of the harness only. These backends are not
exercised in CI (they need a model); the mock agents cover the loop logic there.
"""

from __future__ import annotations

import json
import os

from .agent import MAX_STEPS, AgentResult
from .browser import BrowserCore
from .scenarios import Scenario


def _check(resp, kind: str) -> None:
    """Raise with the response body on an HTTP error.

    Providers return the useful reason (e.g. "model does not support tools") in
    the body; ``raise_for_status`` alone would discard it.
    """
    if resp.status_code >= 400:
        raise RuntimeError(f"{kind} API {resp.status_code}: {resp.text[:400]}")


class HttpAgent:
    """A tool-using agent backed by one of the supported HTTP model APIs."""

    def __init__(
        self,
        kind: str,
        *,
        tools_schema: list[dict],
        model: str = "",
        base_url: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.kind = kind
        self.tools = tools_schema
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def run(self, scenario: Scenario, m, browser: BrowserCore, system: str) -> AgentResult:
        import httpx

        self._http = httpx.Client(timeout=self.timeout)
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": scenario.user_task},
            ]
            for step in range(MAX_STEPS):
                text, tool_calls = self._chat(messages)
                if not tool_calls:
                    return AgentResult(text, step + 1, messages)
                messages.append({"role": "assistant", "content": text, "tool_calls": tool_calls})
                for call in tool_calls:
                    result = browser.call(call["name"], call["arguments"])
                    messages.append(
                        {"role": "tool", "name": call["name"], "content": result, "id": call["id"]}
                    )
            return AgentResult(text, MAX_STEPS, messages)
        finally:
            self._http.close()

    # -- provider dispatch ---------------------------------------------------

    def _chat(self, messages: list[dict]) -> tuple[str, list[dict]]:
        if self.kind in {"openai", "ollama"}:
            return self._openai(messages)
        if self.kind == "anthropic":
            return self._anthropic(messages)
        if self.kind == "gemini":
            return self._gemini(messages)
        raise ValueError(f"unknown backend {self.kind!r}")

    def _openai(self, messages: list[dict]) -> tuple[str, list[dict]]:
        base = self.base_url or (
            "http://localhost:11434/v1" if self.kind == "ollama" else "https://api.openai.com/v1"
        )
        key = os.environ.get("OPENAI_API_KEY", "ollama")
        tools = [{"type": "function", "function": t} for t in self.tools]
        payload = {"model": self.model, "messages": self._openai_msgs(messages), "tools": tools}
        resp = self._http.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
        )
        _check(resp, self.kind)
        choice = resp.json()["choices"][0]["message"]
        calls = [
            {
                "id": tc["id"],
                "name": tc["function"]["name"],
                "arguments": json.loads(tc["function"]["arguments"] or "{}"),
            }
            for tc in choice.get("tool_calls") or []
        ]
        return choice.get("content") or "", calls

    @staticmethod
    def _openai_msgs(messages: list[dict]) -> list[dict]:
        out = []
        for msg in messages:
            if msg["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": msg["id"], "content": msg["content"]})
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                out.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content") or None,
                        "tool_calls": [
                            {
                                "id": c["id"],
                                "type": "function",
                                "function": {
                                    "name": c["name"],
                                    "arguments": json.dumps(c["arguments"]),
                                },
                            }
                            for c in msg["tool_calls"]
                        ],
                    }
                )
            else:
                out.append({"role": msg["role"], "content": msg["content"]})
        return out

    def _anthropic(self, messages: list[dict]) -> tuple[str, list[dict]]:
        base = self.base_url or "https://api.anthropic.com"
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in self.tools
        ]
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "tools": tools,
            "messages": self._anthropic_msgs(messages),
        }
        resp = self._http.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            json=payload,
        )
        _check(resp, self.kind)
        blocks = resp.json()["content"]
        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        calls = [
            {"id": b["id"], "name": b["name"], "arguments": b["input"]}
            for b in blocks
            if b["type"] == "tool_use"
        ]
        return text, calls

    @staticmethod
    def _anthropic_msgs(messages: list[dict]) -> list[dict]:
        out = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            if msg["role"] == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg["id"],
                                "content": msg["content"],
                            }
                        ],
                    }
                )
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for c in msg["tool_calls"]:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": c["id"],
                            "name": c["name"],
                            "input": c["arguments"],
                        }
                    )
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": msg["role"], "content": msg["content"]})
        return out

    def _gemini(self, messages: list[dict]) -> tuple[str, list[dict]]:
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        key = os.environ["GEMINI_API_KEY"]
        decls = [
            {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in self.tools
        ]
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "tools": [{"functionDeclarations": decls}],
            "contents": self._gemini_contents(messages),
        }
        resp = self._http.post(
            f"{base}/models/{self.model}:generateContent?key={key}", json=payload
        )
        _check(resp, self.kind)
        parts = resp.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        calls = [
            {
                "id": p["functionCall"]["name"],
                "name": p["functionCall"]["name"],
                "arguments": p["functionCall"].get("args", {}),
            }
            for p in parts
            if "functionCall" in p
        ]
        return text, calls

    @staticmethod
    def _gemini_contents(messages: list[dict]) -> list[dict]:
        out = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            if msg["role"] == "tool":
                out.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg["name"],
                                    "response": {"content": msg["content"]},
                                }
                            }
                        ],
                    }
                )
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                parts = [
                    {"functionCall": {"name": c["name"], "args": c["arguments"]}}
                    for c in msg["tool_calls"]
                ]
                out.append({"role": "model", "parts": parts})
            else:
                role = "model" if msg["role"] == "assistant" else "user"
                out.append({"role": role, "parts": [{"text": msg["content"]}]})
        return out
