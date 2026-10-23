"""Scenario model and loader.

A scenario is the full input to one experiment cell: the user task, the search
ranking the lab returns, the pages that exist, where the attacker payload hides,
and the network conditions (resolver and TLS policy). Scenarios are plain data
(YAML on disk) so the experiment is auditable and reproducible.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .attacks import OBJECTIVES, VECTORS


@dataclass(frozen=True)
class Inject:
    """Marks that a page carries the scenario's attacker payload via ``vector``."""

    vector: str


@dataclass(frozen=True)
class PageSpec:
    """One page served by the lab web servers."""

    host: str
    path: str
    title: str
    body_md: str
    inject: Inject | None = None
    authority: str | None = None  # e.g. "official", "verified" - a fake trust badge


@dataclass(frozen=True)
class SearchResult:
    """One ranked search result pointing at a lab page."""

    host: str
    path: str
    rank: int
    title: str | None = None
    snippet: str | None = None
    authority_badge: str | None = None


@dataclass(frozen=True)
class SearchQuery:
    """The ranked results the search engine returns for ``query``."""

    query: str
    results: tuple[SearchResult, ...]


@dataclass(frozen=True)
class Scenario:
    """A complete experiment cell."""

    id: str
    family: str
    title: str
    description: str
    objective: str
    user_task: str
    true_version: str
    attacker_domain: str
    resolver: str = "clean"  # clean | poisoned
    tls: str = "plain"  # plain | verify | noverify
    task_format: str = "text"
    must_include: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()
    queries: tuple[SearchQuery, ...] = ()
    pages: tuple[PageSpec, ...] = ()
    poisoned_names: tuple[str, ...] = ()  # hosts the poisoned resolver redirects

    def hosts(self) -> set[str]:
        return {p.host for p in self.pages}

    def injected_pages(self) -> list[PageSpec]:
        return [p for p in self.pages if p.inject is not None]


_VALID_RESOLVER = {"clean", "poisoned"}
_VALID_TLS = {"plain", "verify", "noverify"}


def _parse_results(raw: Iterable[dict]) -> tuple[SearchResult, ...]:
    out = []
    for item in raw:
        out.append(
            SearchResult(
                host=item["host"],
                path=item.get("path", "/"),
                rank=int(item["rank"]),
                title=item.get("title"),
                snippet=item.get("snippet"),
                authority_badge=item.get("authority_badge"),
            )
        )
    return tuple(sorted(out, key=lambda r: r.rank))


def _parse_pages(raw: Iterable[dict]) -> tuple[PageSpec, ...]:
    out = []
    for item in raw:
        inject = None
        if item.get("inject"):
            vector = item["inject"]["vector"]
            if vector not in VECTORS and vector != "tool_description":
                raise ValueError(f"page {item.get('path')!r}: unknown vector {vector!r}")
            inject = Inject(vector=vector)
        out.append(
            PageSpec(
                host=item["host"],
                path=item.get("path", "/"),
                title=item["title"],
                body_md=item.get("body_md", ""),
                inject=inject,
                authority=item.get("authority"),
            )
        )
    return tuple(out)


def from_dict(data: dict) -> Scenario:
    """Build and validate a :class:`Scenario` from a parsed YAML/JSON mapping."""
    objective = data["objective"]
    if objective not in OBJECTIVES:
        raise ValueError(f"scenario {data.get('id')!r}: unknown objective {objective!r}")
    resolver = data.get("resolver", "clean")
    tls = data.get("tls", "plain")
    if resolver not in _VALID_RESOLVER:
        raise ValueError(f"resolver must be one of {_VALID_RESOLVER}")
    if tls not in _VALID_TLS:
        raise ValueError(f"tls must be one of {_VALID_TLS}")
    task = data["task"]
    scenario = Scenario(
        id=data["id"],
        family=data["family"],
        title=data["title"],
        description=data.get("description", ""),
        objective=objective,
        user_task=task["user"],
        true_version=str(data.get("true_version", "")),
        attacker_domain=data.get("attacker_domain", "attacker.test"),
        resolver=resolver,
        tls=tls,
        task_format=task.get("format", "text"),
        must_include=tuple(str(x) for x in task.get("must_include", [])),
        must_exclude=tuple(str(x) for x in task.get("must_exclude", [])),
        queries=tuple(
            SearchQuery(query=q["query"], results=_parse_results(q.get("results", [])))
            for q in data.get("search", [])
        ),
        pages=_parse_pages(data.get("pages", [])),
        poisoned_names=tuple(data.get("poisoned_names", [])),
    )
    _check_consistency(scenario)
    return scenario


def _check_consistency(s: Scenario) -> None:
    known = {(p.host, p.path.rstrip("/") or "/") for p in s.pages}
    for q in s.queries:
        for r in q.results:
            if (r.host, r.path.rstrip("/") or "/") not in known:
                raise ValueError(f"{s.id}: result {r.host}{r.path} has no page")
    if s.resolver == "poisoned" and not s.poisoned_names:
        raise ValueError(f"{s.id}: poisoned resolver but no poisoned_names")


def load_file(path: str | Path) -> Scenario:
    """Load one scenario from a YAML (preferred) or JSON file."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # optional; only needed to read YAML scenarios

        data = yaml.safe_load(text)
    except ModuleNotFoundError:
        data = json.loads(text)
    return from_dict(data)


def load_dir(path: str | Path) -> list[Scenario]:
    """Load every ``*.yaml`` / ``*.yml`` / ``*.json`` scenario in a directory."""
    root = Path(path)
    files = sorted(
        p for p in root.iterdir() if p.suffix in {".yaml", ".yml", ".json"} and p.is_file()
    )
    return [load_file(p) for p in files]
