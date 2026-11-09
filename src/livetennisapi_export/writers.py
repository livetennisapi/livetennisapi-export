"""Write rows to CSV, JSON Lines or Parquet.

JSON Lines keeps every row exactly as the API sent it, nested objects included.
CSV and Parquet need flat columns, so nested objects become dotted column names
(``players.p1.name``) and lists become JSON text (``score.sets`` is ``"[2, 1]"``).
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import IO, Any

FORMATS = ("csv", "jsonl", "parquet")

_PARQUET_HINT = 'Parquet output needs pandas and pyarrow: pip install "livetennisapi-export[parquet]"'

_EXTENSIONS = {
    ".csv": "csv",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".parquet": "parquet",
    ".pq": "parquet",
}


def infer_format(path: str | Path) -> str:
    """The format named by a file extension. Raises ``ValueError`` if there is none."""
    suffix = Path(str(path)).suffix.lower()
    try:
        return _EXTENSIONS[suffix]
    except KeyError:
        raise ValueError(
            f"cannot tell the format from {str(path)!r}; use a .csv, .jsonl or .parquet name, or pass a format"
        ) from None


def flatten(row: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Nested objects to dotted keys. Lists become JSON text, scalars stay as they are."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            if value:
                out.update(flatten(value, f"{name}."))
            else:
                out[name] = None
        elif isinstance(value, (list, tuple)):
            out[name] = json.dumps(list(value), ensure_ascii=False)
        else:
            out[name] = value
    return out


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(rows: Iterable[Mapping[str, Any]], out: IO[str]) -> int:
    flat = [flatten(r) for r in rows]
    columns = _columns(flat)
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="raise", lineterminator="\n")
    if columns:
        writer.writeheader()
    for row in flat:
        writer.writerow({c: _csv_value(row.get(c)) for c in columns})
    return len(flat)


def write_jsonl(rows: Iterable[Mapping[str, Any]], out: IO[str]) -> int:
    n = 0
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        out.write("\n")
        n += 1
    return n


def to_dataframe(rows: Iterable[Mapping[str, Any]]):
    """Flattened rows as a pandas DataFrame. Needs the ``parquet`` extra."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(_PARQUET_HINT) from exc

    flat = [flatten(r) for r in rows]
    frame = pd.DataFrame.from_records(flat, columns=_columns(flat))
    # Parquet wants one type per column. The API keeps types stable per field,
    # but a column can still mix, say, int and str across rows of an evolving
    # field. Store such a column as text rather than fail the export.
    for column in frame.columns:
        kinds = {type(v) for v in frame[column] if v is not None and v == v}
        if len(kinds) > 1 and not kinds <= {int, float}:
            frame[column] = frame[column].map(lambda v: None if v is None or v != v else str(v))
    return frame


def write_parquet(rows: Iterable[Mapping[str, Any]], path: str | Path) -> int:
    frame = to_dataframe(rows)
    try:
        frame.to_parquet(path, index=False)
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(_PARQUET_HINT) from exc
    return len(frame)


def write(rows: Iterable[Mapping[str, Any]], path: str | Path, fmt: str | None = None) -> int:
    """Write ``rows`` to ``path`` and return the row count. ``"-"`` means stdout (CSV or JSON Lines)."""
    rows = list(rows)
    if fmt is None:
        if str(path) == "-":
            raise ValueError("writing to stdout needs an explicit format")
        fmt = infer_format(path)
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}")

    if fmt == "parquet":
        if str(path) == "-":
            raise ValueError("Parquet is binary and cannot go to stdout; give a file name")
        return write_parquet(rows, path)

    writer = write_csv if fmt == "csv" else write_jsonl
    if str(path) == "-":
        return writer(rows, sys.stdout)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        return writer(rows, handle)
