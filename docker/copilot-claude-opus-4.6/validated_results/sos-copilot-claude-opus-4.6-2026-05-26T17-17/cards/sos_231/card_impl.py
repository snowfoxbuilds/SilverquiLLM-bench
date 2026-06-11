"""Card implementation for Splatter Technique."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Creature
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SplatterTechnique(Sorcery):
    """Splatter Technique — {1}{U}{U}{R}{R} — Sorcery.

    Choose one —
    • Draw four cards.
    • Splatter Technique deals 4 damage to each creature and planeswalker.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Splatter Technique")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}{R}{R}"))
        super().__init__(**kwargs)
        self.mode: int = 0  # 0 = draw four, 1 = damage

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import draw_card, deal_damage
        from engine.state_based_actions import resolve_state_based_actions

        controller = self.controller

        if self.mode == 0:
            # Draw four cards
            for _ in range(4):
                draw_card(game, controller)
        elif self.mode == 1:
            # Deal 4 damage to each creature and planeswalker
            targets = []
            for player in game.players:
                bf = game.get_battlefield(player)
                for perm in bf.get_all():
                    card_types = getattr(perm, "card_types", set())
                    if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                        targets.append(perm)
            for target in targets:
                deal_damage(game, self, target, 4)
            # Check SBAs to destroy creatures with lethal damage
            resolve_state_based_actions(game)
