"""Card implementation for Preposterous Proportions."""

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


class PreposterousProportions(Sorcery):
    """Preposterous Proportions — {5}{G}{G} — Sorcery.

    Creatures you control get +10/+10 and gain vigilance until end of turn.

    FDN collector number 109.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Preposterous Proportions")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control get +10/+10 and gain vigilance until "
            "end of turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """All creatures you control get +10/+10 and vigilance until EOT."""
        controller = self.controller
        if controller is None:
            return

        # Snapshot creatures at resolution time
        bf = game.get_battlefield(controller)
        creatures = [
            obj for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ]

        def _apply_pt(game: Any) -> None:
            for c in creatures:
                for player in game.players:
                    if game.get_battlefield(player).contains(c):
                        c.base_power += 10
                        c.base_toughness += 10
                        break

        def _apply_vigilance(game: Any) -> None:
            for c in creatures:
                for player in game.players:
                    if game.get_battlefield(player).contains(c):
                        c.keywords = c.keywords | Keyword.VIGILANCE
                        break

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_END_OF_TURN,
        ))
        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_vigilance,
            duration=DURATION_END_OF_TURN,
        ))
