"""Card implementation for WitheringCurse."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class WitheringCurse(Sorcery):
    """Withering Curse — {1}{B}{B} — All creatures get -2/-2 until end of turn.

    The Infusion ability is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Withering Curse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "All creatures get -2/-2 until end of turn.\n"
            "Infusion — If you gained life this turn, destroy all creatures "
            "instead.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        def _apply_debuff(game: GameState) -> None:
            for player in game.players:
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.base_power -= 2
                        obj.base_toughness -= 2

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_debuff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


__all__ = ["WitheringCurse"]
