"""Card-facing Player Query helpers.

Card implementations raise choices through these helpers instead of calling a
player ``choose_*`` method (there is none — the Player ABC exposes only
``answer``). Each helper builds a Player Query, routes it through ``ask`` (which
boundary-validates it and validates the answer), and maps the answer back to the
chosen game object / value. ``source_card`` (the implementing card) supplies the
query's source ref so a test/replay Intent can route by card name.
"""

from __future__ import annotations

from typing import Any, Iterable

from engine.decisions import Decision, GameRef
from engine.queries import PlayerQuery, ask
from engine.refs_registry import object_options
from engine.types import Zone


def _source(card: Any) -> tuple:
    """The query's source refs — the implementing card's printed identity."""
    name = getattr(card, "name", None) if card is not None else None
    if not isinstance(name, str) or not name:
        return ()
    return (Decision.obj(ref=GameRef(card=frozenset({("name", name)})), name=name),)


def _zone_token(game: Any, obj: Any) -> str:
    """Find which zone ``obj`` currently lives in (defaults to battlefield)."""
    for player in game.players:
        for zone in Zone:
            if zone in player.zones and player.zones[zone].contains(obj):
                return zone.value
    return "battlefield"


def choose_object(
    game: Any,
    player: Any,
    candidates: Iterable[Any],
    prompt: str,
    *,
    source_card: Any = None,
    min: int = 1,
    max: int = 1,
    optional: bool = False,
) -> Any:
    """Raise an OBJECT Player Query over ``candidates``; return chosen object(s).

    ``max == 1`` returns a single object (or ``None`` if declined / no
    candidates); ``max > 1`` returns a list. ``optional`` (or ``min == 0``)
    allows a decline.
    """
    cands = list(candidates)
    items = [
        (c, _zone_token(game, c), game.refs.seat_of(getattr(c, "controller", None)))
        for c in cands
    ]
    options, by_decision = object_options(game.refs, items)
    if not options:
        return None if max == 1 else []
    lo = 0 if optional else min
    hi = max if max <= len(options) else len(options)
    if lo > hi:
        lo = hi
    query = PlayerQuery(
        source=_source(source_card),
        prompt=prompt,
        options=options,
        min=lo,
        max=hi,
    )
    answer = ask(player, query)
    chosen = [by_decision[d] for d in answer.selected]
    if max == 1:
        return chosen[0] if chosen else None
    return chosen


def query_yes_no(game: Any, player: Any, prompt: str, *, source_card: Any = None) -> bool:
    """Raise a BOOL Player Query; return True for yes, False for no."""
    query = PlayerQuery(
        source=_source(source_card),
        prompt=prompt,
        options=(Decision.yes(), Decision.no()),
        min=1,
        max=1,
    )
    answer = ask(player, query)
    return ("value", True) in answer.selected[0].attrs


def choose_mode(
    game: Any,
    player: Any,
    mode_names: Iterable[Any],
    prompt: str,
    *,
    source_card: Any = None,
) -> Any:
    """Raise a MODE Player Query over named modes; return the chosen name."""
    names = list(mode_names)
    options = tuple(Decision.mode(str(n), index=i) for i, n in enumerate(names))
    query = PlayerQuery(
        source=_source(source_card),
        prompt=prompt,
        options=options,
        min=1,
        max=1,
    )
    answer = ask(player, query)
    idx = dict(answer.selected[0].attrs)["index"]
    return names[idx]


def choose_color(
    game: Any,
    player: Any,
    prompt: str,
    *,
    colors: Iterable[str] = ("W", "U", "B", "R", "G"),
    source_card: Any = None,
) -> str:
    """Raise a COLOR Player Query; return the chosen single-letter color."""
    options = tuple(Decision.color(c) for c in colors)
    query = PlayerQuery(
        source=_source(source_card),
        prompt=prompt,
        options=options,
        min=1,
        max=1,
    )
    answer = ask(player, query)
    return dict(answer.selected[0].attrs)["color"]
