"""Card implementation for Overrun."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class Overrun(Sorcery):
    """Overrun — {2}{G}{G}{G} — Sorcery.

    Creatures you control get +3/+3 and gain trample until end of turn.

    FDN collector number 230.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Overrun")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control get +3/+3 and gain trample until "
            "end of turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Grant +3/+3 and trample until end of turn."""
        controller = self.controller
        if controller is None:
            return

        # P/T boost
        def _apply_pt(game: Any) -> None:
            if controller is None:
                return
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.modified_power += 3
                    obj.modified_toughness += 3

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_END_OF_TURN,
        ))

        # Trample
        def _apply_trample(game: Any) -> None:
            if controller is None:
                return
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.keywords = obj.keywords | Keyword.TRAMPLE

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_trample,
            duration=DURATION_END_OF_TURN,
        ))
