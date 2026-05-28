"""Card implementation for Axgard Cavalry."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True

class AxgardCavalry(Creature):
    """Axgard Cavalry — {1}{R} — 2/2 — Dwarf Berserker

    {T}: Target creature gains haste until end of turn.

    FDN collector number 189.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Axgard Cavalry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Berserker"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{T}: Target creature gains haste until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            target = getattr(source, "_current_target", None)
            if target is not None:
                target.summoning_sick = False
                # Add haste keyword
                kw = getattr(target, "keywords", Keyword(0))
                target.keywords = kw | Keyword.HASTE

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Target creature gains haste until end of turn.",
        )]
