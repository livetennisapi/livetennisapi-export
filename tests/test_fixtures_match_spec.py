"""Every fixture must validate against the response schema the spec gives for its endpoint.

The spec is OpenAPI 3.1, whose schemas are JSON Schema 2020-12, so the whole
document is registered as one resource and each response schema is reached by
JSON pointer. A fixture that drifts from the spec fails here.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from livetennisapi_export import cli
from livetennisapi_export.datasets import DATASETS

from conftest import FIXTURES, load

SPEC_URI = "urn:livetennisapi:openapi"


def _pointer(path: str, status: str = "200") -> str:
    escaped = path.replace("~", "~0").replace("/", "~1")
    return f"{SPEC_URI}#/paths/{escaped}/get/responses/{status}/content/application~1json/schema"


CASES = [
    ("matches_page1.json", "/matches", "200"),
    ("matches_page2.json", "/matches", "200"),
    ("fixtures.json", "/fixtures", "200"),
    ("players.json", "/players", "200"),
    ("player_101.json", "/players/{playerId}", "200"),
    ("player_202.json", "/players/{playerId}", "200"),
    ("rankings_atp.json", "/rankings", "200"),
    ("tournaments.json", "/tournaments", "200"),
    ("upgrade_required.json", "/rankings", "403"),
]


@pytest.fixture(scope="module")
def registry(spec):
    return Registry().with_resource(SPEC_URI, Resource.from_contents(spec, default_specification=DRAFT202012))


def test_every_fixture_file_is_covered():
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    assert on_disk == {name for name, _, _ in CASES}


@pytest.mark.parametrize(("name", "path", "status"), CASES)
def test_fixture_validates_against_spec(registry, spec, name, path, status):
    assert path in spec["paths"], f"{path} is not in the spec"
    if status != "200":
        # Error responses are a $ref to components/responses; follow it.
        ref = spec["paths"][path]["get"]["responses"][status]["$ref"]
        schema_ref = f"{SPEC_URI}#{ref.lstrip('#')}/content/application~1json/schema"
    else:
        schema_ref = _pointer(path, status)
    validator = Draft202012Validator({"$ref": schema_ref}, registry=registry)
    errors = sorted(validator.iter_errors(load(name)), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_every_dataset_path_exists_in_spec(spec):
    for d in DATASETS.values():
        assert d.path in spec["paths"], d.path
        assert "get" in spec["paths"][d.path]


def _parameters(spec, path):
    """The operation's parameters, with ``#/components/parameters/...`` refs followed."""
    out = []
    for p in spec["paths"][path]["get"].get("parameters", []):
        if "$ref" in p:
            node = spec
            for part in p["$ref"].lstrip("#/").split("/"):
                node = node[part]
            p = node
        out.append(p)
    return out


def _enum(spec, path, name):
    for p in _parameters(spec, path):
        if p.get("name") == name:
            schema = p["schema"]
            return tuple(schema.get("enum") or schema["items"]["enum"])
    raise AssertionError(f"{path} has no parameter {name}")


def test_cli_choices_match_spec(spec):
    assert _enum(spec, "/matches", "status") == cli.STATUSES
    assert _enum(spec, "/matches", "tour") == cli.TOURS
    assert _enum(spec, "/matches", "draw") == cli.DRAWS
    assert _enum(spec, "/fixtures", "tour") == cli.TOURS
    assert _enum(spec, "/rankings", "tour") == cli.RANKING_TOURS
    assert _enum(spec, "/rankings", "surface") == cli.SURFACES
    # utr is left out on purpose: the spec says it has no listing.
    assert set(cli.RANKING_SYSTEMS) == set(_enum(spec, "/rankings", "system")) - {"utr"}


def test_parameters_sent_exist_in_spec(spec):
    wire = {"from_": "from", "ids": None}
    for d in DATASETS.values():
        names = {p["name"] for p in _parameters(spec, d.path)}
        for param in d.params:
            sent = wire.get(param, param)
            if sent is not None:
                assert sent in names, f"{d.path} has no parameter {sent}"
