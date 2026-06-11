"""Card implementation for Pox Plague."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PoxPlague(Sorcery):
    """Pox Plague — {B}{B}{B}{B}{B} — Sorcery.

    Each player loses half their life, then discards half the cards in their
    hand, then sacrifices half the permanents they control of their choice.
    Round down each time.
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

    def on_resolve(self, game: "GameState") -> None:
        """Execute pox effect for all players."""
        from engine.game import sacrifice, discard

        for player in game.players:
            # Lose half life rounded down
            life_loss = player.life // 2
            player.life -= life_loss

        for player in game.players:
            # Discard half hand rounded down
            hand = game.get_hand(player)
            hand_cards = list(hand.get_all())
            num_discard = len(hand_cards) // 2
            for i in range(num_discard):
                card = hand_cards[-(i + 1)]
                discard(game, player, card)

        for player in game.players:
            # Sacrifice half permanents rounded down
            bf = game.get_battlefield(player)
            permanents = list(bf.get_all())
            num_sacrifice = len(permanents) // 2
            for i in range(num_sacrifice):
                perm = permanents[-(i + 1)]
                sacrifice(game, player, perm)
