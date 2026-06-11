"""Card implementation for Killian's Confidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Creature
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class KilliansConfidence(Sorcery):
    """Killian's Confidence — {W}{B} — Sorcery.

    Target creature gets +1/+1 until end of turn. Draw a card.
    Whenever one or more creatures you control deal combat damage to a player,
    you may pay {W/B}. If you do, return this card from your graveyard to your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Killian's Confidence")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Target creature gets +1/+1 until end of turn. Draw a card."""
        targets = getattr(self, "chosen_targets", None) or []
        if targets:
            target = targets[0]
            # +1/+1 until end of turn
            bonus_p = getattr(target, "_temp_power_bonus", 0)
            target._temp_power_bonus = bonus_p + 1
            bonus_t = getattr(target, "_temp_toughness_bonus", 0)
            target._temp_toughness_bonus = bonus_t + 1

        # Draw a card
        controller = self.controller
        library = game.get_library(controller)
        lib_cards = library.get_all()
        if lib_cards:
            top_card = lib_cards[-1]
            library.remove(top_card)
            game.get_hand(controller).add(top_card)

    def on_combat_damage_to_player(self, game: "GameState", attacking_player: Any) -> None:
        """Graveyard trigger: when creatures deal combat damage, may pay to return to hand."""
        # Only triggers if this card is in the graveyard of the attacking player
        if attacking_player is not self.owner:
            return

        graveyard = game.get_graveyard(self.owner)
        if self not in graveyard:
            return

        # Check if player can pay {W/B} (one white or one black mana)
        mana_pool = game.get_mana_pool(self.owner)
        can_pay = (mana_pool.get(ManaType.WHITE, 0) > 0 or
                   mana_pool.get(ManaType.BLACK, 0) > 0)

        if can_pay:
            # Pay the mana (prefer white, then black) by using pay with a ManaCost
            from engine.types import ManaCost as _MC
            if mana_pool.get(ManaType.WHITE, 0) > 0:
                cost = _MC(pips={ManaType.WHITE: 1})
            else:
                cost = _MC(pips={ManaType.BLACK: 1})
            mana_pool.pay(cost)
            # Return to hand
            graveyard.remove(self)
            game.get_hand(self.owner).add(self)
