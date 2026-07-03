"""Card implementation for Claws Out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ClawsOut(Instant):
    """Claws Out — {3}{W}{ Instant.W} 

    Affinity for Cats (This spell costs {1} less to cast for each Cat
    you control.)
    Creatures you control get +2/+2 until end of turn.

    FDN collector number 6.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Claws Out")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Affinity for Cats\n"
            "Creatures you control get +2/+2 until end of turn.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for Cats: reduce cost by 1 for each Cat you control."""
        controller = self.controller
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        count = 0
        for obj in battlefield.get_all():
            if "Cat" in getattr(obj, "subtypes", set()):
                count += 1
        return count

    def on_resolve(self, game: GameState) -> None:
        """Creatures you control get +2/+2 until end of turn."""
        source = self
        controller = self.controller
        if controller is None:
            return

        def _apply_buff(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            battlefield = game.get_battlefield(ctrl)
            for obj in battlefield.get_all():
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                obj.modified_power += 2
                obj.modified_toughness += 2

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        ))
