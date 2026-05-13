"""Card implementation for PoxPlague."""

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



class PoxPlague(Sorcery):
    """Pox Plague — {B}{B}{B}{B}{B} — Each player loses half their life,
    then discards half the cards in their hand, then sacrifices half the
    permanents they control. Round down each time.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pox Plague")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}{B}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each player loses half their life, then discards half the cards "
            "in their hand, then sacrifices half the permanents they control "
            "of their choice. Round down each time.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import discard, sacrifice

        for player in game.players:
            # Lose half life (rounded down)
            life_loss = player.life // 2
            player.life -= life_loss

        for player in game.players:
            # Discard half hand (rounded down)
            hand = game.get_hand(player)
            cards = list(hand.get_all())
            to_discard = len(cards) // 2
            for card in cards[:to_discard]:
                discard(game, player, card)

        for player in game.players:
            # Sacrifice half permanents (rounded down)
            permanents = list(game.get_battlefield(player).get_all())
            to_sac = len(permanents) // 2
            for perm in permanents[:to_sac]:
                sacrifice(game, player, perm)


__all__ = ["PoxPlague"]
