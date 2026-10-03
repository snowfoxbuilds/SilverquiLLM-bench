"""Last-known information (rules 603.10a, 608.2h).

An object that leaves the battlefield becomes a new object with no memory of
its previous existence (rule 400.7). Abilities that refer to the object as it
last existed on the battlefield — "dies" triggers, leaves-the-battlefield
triggers, and effects that read the departed permanent's power, counters or
controller — read its last-known information instead.

The engine snapshots each departing permanent immediately before it leaves.
Card code reads departed-object state only through :func:`last_known_info` or
the ``last_known`` field of :class:`~engine.events.LeavesBattlefieldTriggeredEvent`
and :class:`~engine.events.CreatureDiesTriggeredEvent`, never off the moved object.

A pending ability that refers to its source ("this creature's power") keeps
the source's battlefield stint from when it triggered or was activated, and
reads the source through :func:`as_it_exists` when it resolves: the object
itself while that stint lasts, otherwise its snapshot from leaving that stint
(rule 608.2h). A later return and departure never overwrites that snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

from engine.types import CardType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


@dataclass(frozen=True)
class LastKnownInformation:
    """The object as it last existed in the zone it left.

    Attributes:
        card: The Python object, now in its new zone (a new object, rule 400.7).
        zone: The zone it left; ``Zone.BATTLEFIELD`` for every snapshot today.
        power: ``None`` for a non-creature.
        toughness: ``None`` for a non-creature.
        counters: Every counter type it had, including ``"+1/+1"`` and ``"-1/-1"``.
    """

    card: Any
    zone: Zone
    name: str
    owner: Any
    controller: Any
    card_types: frozenset[CardType]
    subtypes: frozenset[str]
    power: int | None
    toughness: int | None
    counters: Mapping[str, int]
    is_token: bool
    is_tapped: bool
    damage_marked: int
    attached_to: Any | None


def snapshot(card: Any, zone: Zone) -> LastKnownInformation:
    """Capture *card*'s current state as it exists in *zone*."""
    card_types = frozenset(getattr(card, "card_types", ()))
    is_creature = CardType.CREATURE in card_types
    return LastKnownInformation(
        card=card,
        zone=zone,
        name=getattr(card, "name", ""),
        owner=getattr(card, "owner", None),
        controller=getattr(card, "controller", None),
        card_types=card_types,
        subtypes=frozenset(getattr(card, "subtypes", ())),
        power=getattr(card, "power", None) if is_creature else None,
        toughness=getattr(card, "toughness", None) if is_creature else None,
        counters=MappingProxyType(dict(getattr(card, "counters", {}))),
        is_token=bool(getattr(card, "is_token", False)),
        is_tapped=bool(getattr(card, "is_tapped", False)),
        damage_marked=getattr(card, "damage_marked", 0),
        attached_to=getattr(card, "attached_to", None),
    )


def lki_key(card: Any) -> int:
    """The ``GameState.last_known`` key for *card*: its ``object_id``, or its
    identity for a duck-typed object without one."""
    return getattr(card, "object_id", None) or id(card)


def last_known_info(game: GameState, card: Any) -> LastKnownInformation | None:
    """Return *card*'s snapshot from its most recent departure from the
    battlefield, or ``None`` if it has never left."""
    return game.last_known.get(lki_key(card))


def as_it_exists(game: GameState, card: Any, stint_id: int | None) -> Any | None:
    """*card* as the object of battlefield stint *stint_id* (rule 608.2h).

    Returns *card* itself while it is still on the battlefield in that stint,
    so later changes to it count; otherwise the snapshot taken when it left
    that stint, which a later return and departure do not overwrite. Returns
    ``None`` if *stint_id* is ``None`` or was never left. Capture *stint_id*
    with :func:`engine.stack.battlefield_stint_id` when the ability triggers
    or is activated.
    """
    from engine.stack import battlefield_stint_id

    if stint_id is None:
        return None
    if battlefield_stint_id(game, card) == stint_id:
        return card
    return game.last_known_by_stint.get(stint_id)


def is_same_object(game: GameState, card: Any, stint_id: int | None) -> bool:
    """Whether *card* is still the battlefield object of stint *stint_id*; an
    ability that acts on "this creature" does nothing to the new object it
    becomes after leaving (rule 400.7)."""
    return as_it_exists(game, card, stint_id) is card
