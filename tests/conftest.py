"""Shared helpers: the vendored spec, the fixtures, and a client on a mock transport.

No test here reaches the network. The client is the real ``livetennisapi``
client; only its HTTP transport is replaced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import httpx
import pytest
import yaml
from livetennisapi import LiveTennisAPI

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
SPEC_PATH = HERE / "spec" / "openapi.yaml"
BASE = "https://api.livetennisapi.com/api/public/v1"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


class Recorder:
    """A mock transport that answers by path and keeps every request it saw."""

    def __init__(self, routes: dict[str, Callable[[httpx.Request], httpx.Response] | list]):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/api/public/v1")
        route = self.routes.get(path)
        if route is None:
            return httpx.Response(404, json={"error": "not_found"})
        if callable(route):
            return route(request)
        # A list of fixture names is served in order, one per request.
        name = route.pop(0) if len(route) > 1 else route[0]
        return httpx.Response(200, json=load(name))


@pytest.fixture
def make_client():
    made: list[LiveTennisAPI] = []

    def factory(routes):
        recorder = Recorder(routes)
        client = LiveTennisAPI("twjp_test", transport=httpx.MockTransport(recorder), max_retries=0)
        client.recorder = recorder  # type: ignore[attr-defined]
        made.append(client)
        return client

    yield factory
    for c in made:
        c.close()
