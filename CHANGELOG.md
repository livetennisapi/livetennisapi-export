# Changelog

## 0.1.0 (unreleased)

First release.

- The `livetennisapi-export` command and a Python API (`fetch`, `write`, `export`, `to_dataframe`).
- Six datasets: `matches`, `fixtures`, `players`, `player`, `rankings` and `tournaments`.
- CSV, JSON Lines and Parquet output. Parquet comes with the `parquet` extra.
- Paging follows `meta.has_more`, and nothing is written until every page has arrived.
