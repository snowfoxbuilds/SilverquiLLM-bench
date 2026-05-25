"""Card implementation for Slagstorm."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature, Instant, Mode, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

class Slagstorm(Sorcery):
    """Slagstorm — {1}{R}{R} — Choose one.

    - Slagstorm deals 3 damage to each creature.
    - Slagstorm deals 3 damage to each player.

    FDN collector number 207.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Slagstorm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Slagstorm deals 3 damage to each creature.\n"
            "• Slagstorm deals 3 damage to each player.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Creatures", description="Slagstorm deals 3 damage to each creature."),
            Mode(name="Players", description="Slagstorm deals 3 damage to each player."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        from benchmarks.sos.workspace.engine.game import deal_damage
        if mode == 0:
            for player in game.players:
                for obj in list(game.get_battlefield(player).get_all()):
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        deal_damage(game, self, obj, 3)
        elif mode == 1:
            for player in game.players:
                deal_damage(game, self, player, 3)
