#!/bin/sh
# Copy the current OpenAPI spec into tests/spec and record the commit it came from.
# Run the tests afterwards: a fixture that no longer matches the spec fails there.
set -eu
cd "$(dirname "$0")/.."
sha=$(git ls-remote https://github.com/livetennisapi/openapi.git HEAD | cut -f1)
curl -fsSL "https://raw.githubusercontent.com/livetennisapi/openapi/$sha/openapi.yaml" -o tests/spec/openapi.yaml
version=$(python3 -c 'import yaml; print(yaml.safe_load(open("tests/spec/openapi.yaml"))["info"]["version"])')
printf 'https://github.com/livetennisapi/openapi/blob/%s/openapi.yaml\ninfo.version %s, copied %s\n' \
    "$sha" "$version" "$(date -u +%Y-%m-%d)" > tests/spec/SOURCE
cat tests/spec/SOURCE
