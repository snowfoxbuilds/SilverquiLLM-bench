"""Card implementation for Pox Plague."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.events import LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import discard, sacrifice
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PoxPlague(Sorcery):
    """Pox Plague."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pox Plague")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}{B}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each player loses half their life, then discards half the cards in their hand, "
            "then sacrifices half the permanents they control of their choice. Round down "
            "each time.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        for player in game.players:
            amount_lost = player.life // 2
            player.life -= amount_lost
            if amount_lost > 0:
                game.trigger_manager.fire_event(
                    game,
                    LosesLifeTriggeredEvent(player=player, amount=amount_lost),
                )

        for player in game.players:
            hand = game.get_hand(player)
            for _ in range(len(hand) // 2):
                cards = hand.get_all()
                if not cards:
                    break
                try:
                    chosen = player.choose_card(cards, "card to discard")
                except Exception:
                    chosen = cards[0]
                if chosen not in cards:
                    chosen = cards[0]
                discard(game, player, chosen)

        for player in game.players:
            battlefield = game.get_battlefield(player)
            for _ in range(len(battlefield) // 2):
                permanents = battlefield.get_all()
                if not permanents:
                    break
                try:
                    chosen = player.choose_card(permanents, "permanent to sacrifice")
                except Exception:
                    chosen = permanents[0]
                if chosen not in permanents:
                    chosen = permanents[0]
                sacrifice(game, player, chosen)
