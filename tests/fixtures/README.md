# Test fixtures

These are synthetic responses. The names ("Test Player A", "Example Open"), ids and scores are made up for the tests and are not real results.

Each file has the shape the OpenAPI spec gives for its endpoint. `tests/test_fixtures_match_spec.py` validates every file against the response schema in `tests/spec/openapi.yaml`, so a fixture that drifts from the spec fails CI.

`tests/spec/openapi.yaml` is a copy of `openapi.yaml` from https://github.com/livetennisapi/openapi. `tests/spec/SOURCE` records the commit it came from. To refresh it, run `scripts/refresh-spec.sh`.
