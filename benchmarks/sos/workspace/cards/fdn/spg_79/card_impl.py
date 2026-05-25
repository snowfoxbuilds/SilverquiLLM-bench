"""Card implementation for Bloom Tender."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
def _get_colors_of_permanent(obj: Any) -> set[Color]:
    """Return the set of MTG colors for a permanent based on its mana cost."""
    from engine.protection import get_colors
    return get_colors(obj)

class BloomTender(Creature):
    """Bloom Tender — {1}{G} — 1/1 — Elf Druid

    {T}: For each color among permanents you control, add one mana of
    that color.

    SPG collector number 79.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloom Tender")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault(
            "rules_text",
            "{T}: For each color among permanents you control, add one "
            "mana of that color.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return

            # Scan all permanents the controller controls on the battlefield
            bf = game.get_battlefield(controller)
            colors_found: set[Color] = set()
            for perm in bf.get_all():
                colors_found |= _get_colors_of_permanent(perm)

            # Add one mana of each color found
            for color in colors_found:
                mana_type = _COLOR_TO_MANA.get(color)
                if mana_type is not None:
                    controller.mana_pool.add(mana_type, 1)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: For each color among permanents you control, "
                        "add one mana of that color.",
        )]
