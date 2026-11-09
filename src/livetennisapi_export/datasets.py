"""The datasets this package can export, and how each one is paged.

Each dataset is one list endpoint of the Live Tennis API, called through the
official ``livetennisapi`` client. Rows are the response objects exactly as the
server sent them (``Model.to_dict()``), so nothing is renamed or dropped here.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from livetennisapi import LiveTennisAPI

#: The API's maximum ``limit`` on every list endpoint used here.
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class Dataset:
    name: str
    path: str
    method: str
    params: tuple[str, ...]
    tier: str
    summary: str
    paged: bool = True


DATASETS: dict[str, Dataset] = {
    d.name: d
    for d in (
        Dataset(
            name="matches",
            path="/matches",
            method="list_matches",
            params=("status", "tour", "draw", "player", "country", "from_", "to"),
            tier="FREE for live and upcoming. completed and cancelled need BASIC",
            summary="Matches by status, with optional play-date bounds",
        ),
        Dataset(
            name="fixtures",
            path="/fixtures",
            method="list_fixtures",
            params=("tour", "draw"),
            tier="FREE",
            summary="Upcoming scheduled fixtures, earliest first",
        ),
        Dataset(
            name="players",
            path="/players",
            method="search_players",
            params=("search",),
            tier="FREE",
            summary="Player search by name",
        ),
        Dataset(
            name="player",
            path="/players/{playerId}",
            method="get_player",
            params=("ids",),
            tier="FREE",
            summary="Full profiles for one or more player ids",
            paged=False,
        ),
        Dataset(
            name="rankings",
            path="/rankings",
            method="list_rankings",
            params=("system", "as_of", "tour", "surface", "min_matches", "activity_weeks"),
            tier="PRO (system=elo needs ULTRA)",
            summary="One ranking table in rank order (listing mode)",
        ),
        Dataset(
            name="tournaments",
            path="/tournaments",
            method="list_tournaments",
            params=("search", "tour", "draw"),
            tier="FREE",
            summary="Tournament catalogue, the id space Match.tournament_id joins",
        ),
    )
}


def _clean(params: Mapping[str, Any], allowed: Iterable[str]) -> dict[str, Any]:
    allowed = set(allowed)
    unknown = sorted(k for k in params if k not in allowed)
    if unknown:
        raise ValueError(f"unknown parameter(s) {', '.join(unknown)}; this dataset takes {', '.join(sorted(allowed))}")
    return {k: v for k, v in params.items() if v is not None}


def iter_rows(
    dataset: str,
    *,
    client: LiveTennisAPI,
    max_rows: int | None = None,
    page_size: int = MAX_PAGE_SIZE,
    **params: Any,
) -> Iterator[dict[str, Any]]:
    """Yield every row of ``dataset``, page by page.

    Paging follows ``meta.has_more``, which the spec names as the end-of-data
    signal (``total`` is null on completed and cancelled listings). A response
    without ``meta`` falls back to stopping on a short page.
    """
    try:
        spec = DATASETS[dataset]
    except KeyError:
        raise ValueError(f"unknown dataset {dataset!r}; choose from {', '.join(DATASETS)}") from None

    params = _clean(params, spec.params)
    if max_rows is not None and max_rows < 1:
        return
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    fn = getattr(client, spec.method)
    emitted = 0

    if not spec.paged:
        ids = params.get("ids") or []
        if not ids:
            raise ValueError("the player dataset needs at least one player id")
        for player_id in ids:
            obj = fn(int(player_id))
            if obj is None:
                continue
            yield obj.to_dict()
            emitted += 1
            if max_rows is not None and emitted >= max_rows:
                return
        return

    if dataset == "rankings" and not params.get("system"):
        # The listing mode (no ``player``) returns the table for exactly one
        # system, per the spec. Say so here instead of sending a bad request.
        raise ValueError("rankings needs one system, for example system='atp'")
    if dataset == "rankings" and params.get("system") == "utr":
        raise ValueError("utr has no listing (it is a rating, not a ranking)")

    offset = 0
    while True:
        page = fn(limit=page_size, offset=offset, **params)
        items = list(page)
        for item in items:
            yield item.to_dict() if hasattr(item, "to_dict") else dict(item)
            emitted += 1
            if max_rows is not None and emitted >= max_rows:
                return
        meta = page.meta
        has_more = getattr(meta, "has_more", None) if meta is not None else None
        if not items:
            return
        if has_more is False:
            return
        if has_more is None and len(items) < page_size:
            return
        offset += len(items)
