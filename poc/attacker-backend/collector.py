"""Collector - the beacon endpoint that proves the AI followed an injection.

Any request this service receives is recorded. The malicious ``attacker-backend``
forwards a hit here whenever the agent asks the MCP browser to fetch a
``collector.attacker.test`` URL (see ``app.py``), so a row in ``/_log`` is
evidence that the agent obeyed a hidden instruction rather than merely reading
it. The dashboard reads ``/_log`` to display hits in real time.

This is intentionally trivial: in a real attack the collector would be an
internet-facing C2 drop; in the lab it stays on the isolated Docker network.
"""

from __future__ import annotations

import datetime

from fastapi import FastAPI, Request

app = FastAPI(title="collector", docs_url=None, redoc_url=None)

# In-memory log; the lab is short-lived and nothing here needs to persist.
_log: list[dict] = []


@app.get("/_log")
async def get_log() -> list[dict]:
    """Return every beacon hit recorded so far (consumed by the dashboard)."""
    return _log


@app.get("/{path:path}")
async def catch_all(path: str, request: Request) -> dict:
    """Record any request as a beacon hit and return a benign ``ok``."""
    entry = {
        "time": datetime.datetime.now(datetime.UTC).isoformat(),
        "path": f"/{path}",
        "params": dict(request.query_params),
        "headers": {
            k: v for k, v in request.headers.items() if k.startswith("x-") or k == "user-agent"
        },
    }
    _log.append(entry)
    print(f"[BEACON HIT] /{path}?{request.url.query}", flush=True)
    return {"status": "ok"}
