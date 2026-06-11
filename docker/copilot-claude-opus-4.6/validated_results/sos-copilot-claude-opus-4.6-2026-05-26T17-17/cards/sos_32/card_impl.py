"""Card implementation for Soaring Stoneglider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SoaringStoneglider(Creature):
    """Soaring Stoneglider — {2}{W} — Creature — Elephant Cleric — 4/3.

    As an additional cost to cast this spell, exile two cards from your
    graveyard or pay {1}{W}.
    Flying, vigilance
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soaring Stoneglider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Elephant", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, exile two cards from "
            "your graveyard or pay {1}{W}.\nFlying, vigilance",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Can cast if graveyard has 2+ cards OR enough mana for additional {1}{W}."""
        controller = self.controller or self.owner
        if controller is None:
            return True

        graveyard = game.get_graveyard(controller)
        gy_cards = graveyard.get_all()
        if len(gy_cards) >= 2:
            return True

        # Check if player can pay extra {1}{W} on top of base cost
        # Base cost is {2}{W}, additional is {1}{W} => total {3}{W}{W}
        pool = controller.mana_pool
        # We need to check if total mana available covers base + additional
        # Base already gets paid by the casting system, so we check if
        # there's enough for base + additional
        total_available = pool.total()
        white_available = pool.get(ManaType.WHITE)
        # Need at least 2 white (1 for base, 1 for additional) and 3 generic
        # Total needed: {3}{W}{W} = 5 mana, at least 2 white
        if white_available >= 2 and total_available >= 5:
            return True

        return False

    def on_cast(self, game: "GameState") -> None:
        """Pay the additional cost: exile 2 from graveyard or pay {1}{W}."""
        controller = self.controller or self.owner
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        gy_cards = graveyard.get_all()

        if len(gy_cards) >= 2:
            # Prefer exiling from graveyard
            to_exile = gy_cards[:2]
            exile_zone = game.get_exile(controller)
            for card in to_exile:
                graveyard.remove(card)
                card.zone = Zone.EXILE
                exile_zone.add(card)
        else:
            # Pay {1}{W} additional cost
            additional = ManaCost(generic=1, pips={ManaType.WHITE: 1})
            controller.mana_pool.pay(additional)
