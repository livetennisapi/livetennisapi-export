<div align="center">

<img src="https://raw.githubusercontent.com/livetennisapi/.github/main/profile/banner.jpg" alt="Live Tennis API" width="640">

# livetennisapi-export

**Export [Live Tennis API](https://livetennisapi.com) data to CSV, JSON Lines or Parquet.**

Matches, fixtures, players, rankings and tournaments for ATP, WTA, Challenger, ITF and juniors, from the command line or from Python.

[![CI](https://github.com/livetennisapi/livetennisapi-export/actions/workflows/ci.yml/badge.svg)](https://github.com/livetennisapi/livetennisapi-export/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[**Website**](https://livetennisapi.com) · [**Documentation**](https://docs.livetennisapi.com) · [**Pricing**](https://livetennisapi.com/pricing) · [**Changelog**](CHANGELOG.md) · [**Get a free API key**](https://livetennisapi.com/subscribe/free)

</div>

---

## Install

The package is not on PyPI yet. Until it is, install it from GitHub:

```bash
pip install "livetennisapi-export @ git+https://github.com/livetennisapi/livetennisapi-export"
pip install "livetennisapi-export[parquet] @ git+https://github.com/livetennisapi/livetennisapi-export"
```

The second line adds Parquet support.

It is built on the official Python client, [`livetennisapi`](https://github.com/livetennisapi/livetennisapi-python), which pip installs with it. Parquet needs pandas and pyarrow, which the `parquet` extra brings in.

## Set the API key in your environment

You can get a free key at [livetennisapi.com/subscribe/free](https://livetennisapi.com/subscribe/free). Then:

```bash
export LIVETENNISAPI_KEY=twjp_...
```

The command reads the key from that variable only. There is no flag for it, so it stays out of your shell history.

## Command line

The file name picks the format: `.csv`, `.jsonl` (or `.ndjson`) and `.parquet`. Use `-o -` with `-f csv` or `-f jsonl` to write to stdout.

```bash
# Upcoming fixtures on the ATP tour
livetennisapi-export fixtures --tour atp -o fixtures.csv

# Every match completed on one day, as Parquet
livetennisapi-export matches --status completed --date 2026-11-08 -o results.parquet

# Matches in a date range for two players
livetennisapi-export matches --status completed --from 2026-10-01 --to 2026-10-31 --player 101 --player 202 -o oct.jsonl

# Full profiles for a list of player ids (the players search gives you ids)
livetennisapi-export player 101 202 303 -o players.csv

# Player search
livetennisapi-export players alcaraz -o - -f jsonl

# The current WTA ranking table
livetennisapi-export rankings --system wta -o wta.csv

# The tournament catalogue
livetennisapi-export tournaments --tour challenger -o challenger-events.csv
```

`livetennisapi-export DATASET --help` lists every option for a dataset.

## Datasets

| Dataset | Endpoint | Plan |
|---|---|---|
| `matches` | `GET /matches` | FREE for `live` and `upcoming`. `completed` and `cancelled` are part of History and need BASIC |
| `fixtures` | `GET /fixtures` | FREE |
| `players` | `GET /players?search=` | FREE |
| `player` | `GET /players/{playerId}` | FREE |
| `rankings` | `GET /rankings` (one system, rank order) | PRO. `--system elo` needs ULTRA |
| `tournaments` | `GET /tournaments` | FREE |

The plans come from the [OpenAPI spec](https://github.com/livetennisapi/openapi). If your plan does not cover a request, the API answers 403. The command then prints the plan it needs and exits with status 1. [Pricing](https://livetennisapi.com/pricing) has the plans.

The command pages through every result with the API's maximum page size of 200. It stops when `meta.has_more` is false. `--max-rows N` stops sooner. Each page is one request against your quota, so `--max-rows` is worth using on large listings.

## What the files contain

JSON Lines has one object per line, exactly as the API returned it, nested objects and all.

CSV and Parquet need flat columns, so nested objects become dotted column names and lists become JSON text. A match row has columns such as `players.p1.name`, `players.p2.ranking` and `score.sets`, where `score.sets` holds `[2, 1]`. Empty values are empty cells in CSV and nulls in Parquet. The columns follow the fields the API sent, so a field added to the API shows up as a new column with no upgrade.

Nothing is written until every page has arrived. A request that fails halfway leaves no half-written file.

## Python

```python
from livetennisapi_export import export, fetch, write

rows = fetch("fixtures", tour="atp")               # a list of dicts
write(rows, "fixtures.jsonl")

export("matches", "results.csv", status="completed", from_="2026-11-01", to="2026-11-07")
export("player", "players.parquet", ids=[101, 202])
```

`from_` is the `from` parameter, renamed because `from` is a Python keyword. `fetch` and `export` take `api_key=` or read `LIVETENNISAPI_KEY`. They also take `client=` if you already have a `livetennisapi.LiveTennisAPI` set up.

To get a pandas DataFrame with the same flat columns as the CSV:

```python
from livetennisapi_export import fetch, to_dataframe

df = to_dataframe(fetch("rankings", system="atp"))
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The tests never call the API. They run the real client against a mock transport that serves fixtures from `tests/fixtures/`. Every fixture is checked against the response schema in a pinned copy of the OpenAPI spec (`tests/spec/`). The dataset paths, query parameters and CLI choices are checked against it too. `scripts/refresh-spec.sh` pulls the latest spec.

## Links

- Live Tennis API: https://livetennisapi.com
- Documentation: https://docs.livetennisapi.com
- OpenAPI spec: https://github.com/livetennisapi/openapi
- Python client: https://github.com/livetennisapi/livetennisapi-python

MIT licensed. See [LICENSE](LICENSE).
