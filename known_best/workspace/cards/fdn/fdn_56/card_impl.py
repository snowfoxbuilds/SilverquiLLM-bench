"""Card implementation for Billowing Shriekmass."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BillowingShriekmass(Creature):
    """Billowing Shriekmass — {3}{B} — 2/3 — Spirit — Flying.

    When this creature enters, mill three cards.
    Threshold — This creature gets +2/+1 as long as there are seven or
    more cards in your graveyard.

    FDN collector number 56.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Billowing Shriekmass")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Spirit"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, mill three cards.\n"
            "Threshold — This creature gets +2/+1 as long as there are "
            "seven or more cards in your graveyard.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: mill three cards."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        # Mill top 3 (top is end of list)
        for _ in range(3):
            cards = library.get_all()
            if not cards:
                break
            top_card = cards[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)

    def apply_continuous_effect(self, game: "GameState") -> list[ContinuousEffect]:
        """Threshold: +2/+1 if seven or more cards in graveyard.

        Returns the effect list (for direct callers / tests) AND registers
        with the game's effect_manager so the layer system applies it during
        normal gameplay.
        """
        controller = self.controller
        if controller is None:
            return []

        gy = controller.zones[Zone.GRAVEYARD]
        if len(gy.get_all()) < 7:
            return []

        source = self

        def _apply(game: Any) -> None:
            source.modified_power = source.modified_power + 2
            source.modified_toughness = source.modified_toughness + 1

        from engine.continuous_effects import DURATION_PERMANENT

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )

        # Register with the effect_manager so the layer system picks it up.
        if hasattr(game, "effect_manager"):
            # Avoid duplicate registration: only add if not already present.
            existing = game.effect_manager.get_effects_by_source(self)
            if not existing:
                game.effect_manager.add(effect)

        return [effect]
