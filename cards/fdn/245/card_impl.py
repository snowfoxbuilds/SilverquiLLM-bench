"""Card implementation for Ruby, Daring Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, ManaAbility
from engine.types import (
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
)




def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
class RubyDaringTracker(Creature):
    """Ruby, Daring Tracker — {R}{G} — 1/2 — Human Scout

    Haste
    Whenever Ruby attacks while you control a creature with power 4 or
    greater, Ruby gets +2/+2 until end of turn.
    {T}: Add {R} or {G}.

    FDN collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ruby, Daring Tracker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{G}"))
        kwargs.setdefault("subtypes", {"Human", "Scout"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Haste\nWhenever Ruby attacks while you control a creature with "
            "power 4 or greater, Ruby gets +2/+2 until end of turn.\n"
            "{T}: Add {R} or {G}.",
        )
        super().__init__(**kwargs)

    # ENGINE LIMITATION: attack trigger (+2/+2 when attacking with 4+ power creature) not implemented — requires attack event tracking

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _make_effect(mtype: ManaType):
            def _effect(game: Any) -> None:
                controller = source.controller
                if controller is not None:
                    controller.mana_pool.add(mtype, 1)
            return _effect

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(ManaType.RED),
                description="{T}: Add {R}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(ManaType.GREEN),
                description="{T}: Add {G}.",
            ),
        ]
