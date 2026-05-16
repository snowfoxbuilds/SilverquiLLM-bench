"""Card implementation for Elvish Archdruid."""

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
def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class ElvishArchdruid(Creature):
    """Elvish Archdruid — {1}{G}{G} — 2/2 — Elf Druid

    Other Elf creatures you control get +1/+1.
    {T}: Add {G} for each Elf you control.

    FDN collector number 219.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elvish Archdruid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Other Elf creatures you control get +1/+1.\n"
            "{T}: Add {G} for each Elf you control.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            # Count Elves you control (including self)
            elf_count = 0
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and "Elf" in getattr(card, "subtypes", set())
                ):
                    elf_count += 1
            if elf_count > 0:
                controller.mana_pool.add(ManaType.GREEN, elf_count)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: Add {G} for each Elf you control.",
        )]

    def register_triggers(self, game: Any) -> None:
        """Register the static +1/+1 lord effect for other Elves.

        # ENGINE LIMITATION: Static abilities should use the continuous effect
        # layer system. This simplified version applies immediately on ETB.
        """
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_PERMANENT,
            Layer,
            SubLayer,
        )

        source = self

        def _apply(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, source):
                return
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if card is source:
                    continue
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and "Elf" in getattr(card, "subtypes", set())
                ):
                    card.modified_power = card.base_power + 1
                    card.modified_toughness = card.base_toughness + 1

        effect = ContinuousEffect(
            source=source,
            apply_fn=_apply,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFICATION,
            duration=DURATION_PERMANENT,
        )
        game.effect_manager.register(effect)
