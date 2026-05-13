"""Card implementation for Slagstorm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Mode, Sorcery
from engine.game import deal_damage
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


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
        from engine.game import deal_damage
        if mode == 0:
            for player in game.players:
                for obj in list(game.get_battlefield(player).get_all()):
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        deal_damage(game, self, obj, 3)
        elif mode == 1:
            for player in game.players:
                deal_damage(game, self, player, 3)
