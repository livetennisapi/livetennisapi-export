"""Export Live Tennis API data to CSV, JSON Lines or Parquet.

    from livetennisapi_export import export, fetch, write

    rows = fetch("fixtures", tour="atp")            # list of dicts, as the API sent them
    write(rows, "fixtures.csv")                     # or .jsonl, or .parquet with the extra

    export("matches", "upcoming.parquet", status="upcoming")

The API key comes from ``api_key=`` or the ``LIVETENNISAPI_KEY`` environment
variable, the same as the official ``livetennisapi`` client this is built on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from livetennisapi import LiveTennisAPI

from .datasets import DATASETS, MAX_PAGE_SIZE, Dataset, iter_rows
from .writers import FORMATS, flatten, infer_format, to_dataframe, write

__version__ = "0.1.0"

__all__ = [
    "DATASETS",
    "FORMATS",
    "Dataset",
    "__version__",
    "export",
    "fetch",
    "flatten",
    "infer_format",
    "iter_rows",
    "to_dataframe",
    "write",
]


def _client(client: LiveTennisAPI | None, api_key: str | None) -> tuple[LiveTennisAPI, bool]:
    if client is not None:
        return client, False
    return LiveTennisAPI(api_key=api_key), True


def fetch(
    dataset: str,
    *,
    client: LiveTennisAPI | None = None,
    api_key: str | None = None,
    max_rows: int | None = None,
    page_size: int = MAX_PAGE_SIZE,
    **params: Any,
) -> list[dict[str, Any]]:
    """Every row of ``dataset`` as a list of dicts. See ``DATASETS`` for the names and parameters."""
    api, owned = _client(client, api_key)
    try:
        return list(iter_rows(dataset, client=api, max_rows=max_rows, page_size=page_size, **params))
    finally:
        if owned:
            api.close()


def export(
    dataset: str,
    path: str | Path,
    *,
    fmt: str | None = None,
    client: LiveTennisAPI | None = None,
    api_key: str | None = None,
    max_rows: int | None = None,
    page_size: int = MAX_PAGE_SIZE,
    **params: Any,
) -> int:
    """Fetch ``dataset`` and write it to ``path``. Returns the number of rows written.

    Nothing is written until every page has arrived, so a failed request never
    leaves a half-written file behind.
    """
    if fmt is None and str(path) != "-":
        fmt = infer_format(path)
    rows = fetch(dataset, client=client, api_key=api_key, max_rows=max_rows, page_size=page_size, **params)
    return write(rows, path, fmt)
