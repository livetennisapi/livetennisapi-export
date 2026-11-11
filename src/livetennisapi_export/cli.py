"""The ``livetennisapi-export`` command.

    livetennisapi-export fixtures --tour atp -o fixtures.csv
    livetennisapi-export matches --status completed --date 2026-11-08 -o results.parquet
    livetennisapi-export player 101 202 -o players.jsonl

The key is read from ``LIVETENNISAPI_KEY``. There is deliberately no flag for
it, so the key is never part of the export command or its process arguments.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Any

from livetennisapi import LiveTennisAPI
from livetennisapi.errors import APIStatusError, LiveTennisAPIError

from . import __version__, export
from .datasets import DATASETS, MAX_PAGE_SIZE
from .writers import FORMATS

# Enumerations copied from the OpenAPI spec (tests/spec/openapi.yaml). The
# test suite checks them against the spec so they cannot drift silently.
TOURS = ("atp", "wta", "challenger", "itf", "juniors")
DRAWS = ("singles", "doubles")
STATUSES = ("live", "upcoming", "completed", "cancelled")
RANKING_SYSTEMS = ("atp", "wta", "itf_jt", "itf_mt", "itf_wt", "elo", "atp_doubles", "wta_doubles")
RANKING_TOURS = ("atp", "wta")
SURFACES = ("overall", "hard", "clay", "grass")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--output", required=True, help="file to write (.csv, .jsonl or .parquet), or - for stdout")
    p.add_argument("-f", "--format", choices=FORMATS, help="output format when the file name does not say")
    p.add_argument("--max-rows", type=int, help="stop after this many rows")
    p.add_argument(
        "--page-size", type=int, default=MAX_PAGE_SIZE, help=f"rows per request, 1 to {MAX_PAGE_SIZE} (default)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="livetennisapi-export",
        description="Export Live Tennis API data to CSV, JSON Lines or Parquet. Reads the key from LIVETENNISAPI_KEY.",
        epilog="Get a free key at https://livetennisapi.com/subscribe/free. Docs: https://docs.livetennisapi.com",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="dataset", metavar="DATASET", required=True)

    def add(name: str) -> argparse.ArgumentParser:
        d = DATASETS[name]
        return sub.add_parser(name, help=f"{d.summary} ({d.tier})", description=f"{d.summary}. Tier: {d.tier}.")

    p = add("matches")
    p.add_argument("--status", choices=STATUSES, default="upcoming", help="lifecycle status (default: upcoming)")
    p.add_argument("--date", help="one play date, YYYY-MM-DD (sets --from and --to)")
    p.add_argument("--from", dest="from_", help="earliest play date, YYYY-MM-DD or ISO-8601 UTC")
    p.add_argument("--to", help="latest play date, same formats as --from")
    p.add_argument("--tour", choices=TOURS)
    p.add_argument("--draw", choices=DRAWS)
    p.add_argument("--player", type=int, action="append", help="player id, repeatable (max 50)")
    p.add_argument("--country", help="either player's 3-letter country code, lowercase")
    _add_common(p)

    p = add("fixtures")
    p.add_argument("--tour", choices=TOURS)
    p.add_argument("--draw", choices=DRAWS)
    _add_common(p)

    p = add("players")
    p.add_argument("search", help="name or part of a name")
    _add_common(p)

    p = add("player")
    p.add_argument("ids", nargs="+", type=int, metavar="PLAYER_ID", help="one or more player ids")
    _add_common(p)

    p = add("rankings")
    p.add_argument("--system", choices=RANKING_SYSTEMS, required=True)
    p.add_argument("--as-of", dest="as_of", help="YYYY-MM-DD, newest table on or before this date")
    p.add_argument("--tour", choices=RANKING_TOURS, help="required by --system elo")
    p.add_argument("--surface", choices=SURFACES, help="--system elo only")
    p.add_argument("--min-matches", dest="min_matches", type=int, help="--system elo only")
    p.add_argument("--activity-weeks", dest="activity_weeks", type=int, help="--system elo only")
    _add_common(p)

    p = add("tournaments")
    p.add_argument("--search", help="case-insensitive substring of the name")
    p.add_argument("--tour", choices=TOURS)
    p.add_argument("--draw", choices=DRAWS)
    _add_common(p)

    return parser


def _params(args: argparse.Namespace) -> dict[str, Any]:
    allowed = DATASETS[args.dataset].params
    params = {k: getattr(args, k) for k in allowed if getattr(args, k, None) is not None}
    if args.dataset == "matches" and args.date:
        if args.from_ or args.to:
            raise SystemExit("livetennisapi-export: use --date or --from/--to, not both")
        params["from_"] = params["to"] = args.date
    return params


def main(argv: Sequence[str] | None = None, *, client: LiveTennisAPI | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_rows is not None and args.max_rows < 1:
        parser.error("--max-rows must be at least 1")
    if not 1 <= args.page_size <= MAX_PAGE_SIZE:
        parser.error(f"--page-size must be between 1 and {MAX_PAGE_SIZE}")
    if client is None and not os.environ.get("LIVETENNISAPI_KEY", "").strip():
        print(
            "livetennisapi-export: set LIVETENNISAPI_KEY first. A free key: https://livetennisapi.com/subscribe/free",
            file=sys.stderr,
        )
        return 2

    try:
        count = export(
            args.dataset,
            args.output,
            fmt=args.format,
            client=client,
            max_rows=args.max_rows,
            page_size=args.page_size,
            **_params(args),
        )
    except APIStatusError as exc:
        print(f"livetennisapi-export: the API refused the request: {exc}", file=sys.stderr)
        return 1
    except LiveTennisAPIError as exc:
        print(f"livetennisapi-export: {exc}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"livetennisapi-export: {exc}", file=sys.stderr)
        return 2

    if args.output != "-":
        print(f"wrote {count} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
