"""HTTP services for the over-the-wire lab (needs the ``services`` extra).

The automated comparison uses the in-process browser in :mod:`mcplab.runner`,
which models the network faithfully and needs no containers. These services
provide the *wire* variant: real FastAPI web / search / collector endpoints and
a Streamable HTTP MCP Browser, so any MCP client (Claude Desktop, an SDK client)
can connect to the containerised server and browse the lab for interactive
exploration. Scenario and run are carried in the ``X-Lab-Scenario`` /
``X-Lab-Run`` headers the client sets; name-resolution and TLS manipulation are
modelled in the browser's resolver, and the collector exposes ``/_hits`` so a
caller can read the side effects a run produced.

See ``docs/04-methodology.md`` for why the automated path stays in-process.
"""

from __future__ import annotations

import os

from .attacks import markers_for
from .labcore import Collector, Lab
from .scenarios import Scenario, load_dir

_HOST_RE = r"^[a-z0-9.-]{1,253}$"
_SCEN_RE = r"^[a-z0-9-]{1,64}$"


def _scenarios() -> dict[str, Scenario]:
    return {s.id: s for s in load_dir(os.environ.get("MCPLAB_SCENARIOS", "/lab/scenarios"))}


def _lab(scenarios: dict[str, Scenario], collector: Collector, scen_id: str, run: str) -> Lab:
    scenario = scenarios[scen_id]
    markers = markers_for(
        run, attacker_domain=scenario.attacker_domain, true_version=scenario.true_version
    )
    return Lab(scenario, markers, collector)


def build_web_app():  # pragma: no cover - exercised only in the wire stack
    """FastAPI app that renders any lab page for the Host + scenario + run."""
    import re

    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="mcplab-web")
    scenarios = _scenarios()

    @app.get("/{path:path}", response_class=HTMLResponse)
    def serve(
        path: str,
        request: Request,
        x_lab_scenario: str = Header(default="default"),
        x_lab_run: str = Header(default="manual"),
    ):
        host = (request.headers.get("host") or "").split(":")[0]
        if not re.match(_HOST_RE, host) or not re.match(_SCEN_RE, x_lab_scenario):
            raise HTTPException(400, "bad host or scenario")
        if x_lab_scenario not in scenarios:
            raise HTTPException(404, "unknown scenario")
        lab = _lab(scenarios, Collector(), x_lab_scenario, x_lab_run)
        key = (host, "/" + path.rstrip("/") if path else "/")
        html = lab._pages.get((key[0], key[1] or "/"))
        if html is None:
            raise HTTPException(404, "no such page")
        return html

    return app


def build_collector_app():  # pragma: no cover - wire stack only
    """FastAPI app that records beacon hits and exposes them per run."""
    from fastapi import FastAPI, Request

    app = FastAPI(title="mcplab-collector")
    store = Collector()

    @app.get("/_hits/{run_id}")
    def hits(run_id: str):
        return [h.__dict__ for h in store.hits_for(run_id)]

    @app.get("/{path:path}")
    def beacon(path: str, request: Request):
        run = request.query_params.get("run", "manual")
        store.record(str(request.url), run)
        return {"ok": True}

    return app


def serve_app(which: str, host: str = "0.0.0.0", port: int = 8080) -> None:  # pragma: no cover
    import uvicorn

    app = {"web": build_web_app, "collector": build_collector_app}[which]()
    uvicorn.run(app, host=host, port=port)


class WireBrowser:  # pragma: no cover - wire stack only
    """Resolve and fetch real lab URLs over HTTP, applying the scenario policy."""

    def __init__(self, scenario: Scenario, run: str, collector_base: str) -> None:
        self.scenario = scenario
        self.run = run
        self.collector_base = collector_base

    def fetch(self, url: str) -> str:
        from urllib.parse import urlsplit

        import httpx

        parts = urlsplit(url if "://" in url else f"http://{url}")
        host = parts.hostname or ""
        if not host.endswith(".test"):
            return f"error: refusing non-lab host {host!r}"
        resolution = "clean"
        effective = host
        if self.scenario.resolver == "poisoned" and host in self.scenario.poisoned_names:
            resolution, effective = "poisoned", self.scenario.attacker_domain
        if self.scenario.tls == "verify" and resolution == "poisoned":
            return f"error: TLS verification failed for {host}"
        headers = {"Host": effective, "X-Lab-Scenario": self.scenario.id, "X-Lab-Run": self.run}
        base = self.collector_base if host == "collector.test" else os.environ["MCPLAB_WEB_BASE"]
        try:
            resp = httpx.get(f"{base}{parts.path}", headers=headers, timeout=15)
        except httpx.HTTPError as exc:
            return f"error: {exc}"
        return resp.text
