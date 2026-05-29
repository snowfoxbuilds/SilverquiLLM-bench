"""Card implementation for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    """

    # Class-level constant: the casualty threshold this card grants
    casualty_grant: int = 1

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 "
            "or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def apply_casualty_grant(self, game: GameState) -> None:
        """Mark each instant and sorcery in the controller's hand with
        ``casualty_threshold = 1``.

        This method encodes Silverquill's static ability: while it is in play,
        every instant and sorcery spell its controller casts has casualty 1.
        In our implementation we annotate the cards in-hand so that the
        casting machinery (or tests) can read ``casualty_threshold``.
        """
        controller = self.controller
        if controller is None:
            return

        hand_zone = controller.zones[Zone.HAND]
        for card in hand_zone.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                card.casualty_threshold = self.casualty_grant
