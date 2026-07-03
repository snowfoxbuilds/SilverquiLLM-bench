"""Card implementation for Rubble Rouser."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import draw_card, discard
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RubbleRouser(Creature):
    """Rubble Rouser — {2}{R} — Creature — Dwarf Sorcerer (1/4).

    ETB: may discard a card, if you do draw a card.
    {T}, Exile a card from graveyard: Add {R}. Deals 1 damage to each opponent.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rubble Rouser")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Dwarf", "Sorcerer"})
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState", chose_discard: bool = False) -> None:
        """ETB: may discard a card to draw a card."""
        if not chose_discard:
            return
        player = self.controller
        hand = game.get_hand(player)
        cards_in_hand = hand.get_all()
        if not cards_in_hand:
            return
        # Discard the first card in hand
        card_to_discard = cards_in_hand[0]
        discard(game, player, card_to_discard)
        # Draw a card
        draw_card(game, player)

    def activate_mana_ability(self, game: "GameState", exile_target: Any = None) -> None:
        """Tap, exile a card from graveyard: Add {R}, deal 1 to each opponent."""
        if exile_target is None:
            return
        player = self.controller
        # Tap this creature
        self.tapped = True
        # Exile the target card from graveyard
        graveyard = game.get_graveyard(player)
        if graveyard.contains(exile_target):
            graveyard.remove(exile_target)
            exile_zone = game.get_exile(player)
            exile_zone.add(exile_target)
        # Add red mana
        player.mana_pool.add(ManaType.RED, 1)
        # Deal 1 damage to each opponent
        for p in game.players:
            if p is not player:
                p.life -= 1
