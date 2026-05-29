"""Card implementation for Silverquill, the Disputant.

# UNVERIFIED: full casualty sacrifice+copy during casting not fully tested —
# needs optional-additional-cost engine infrastructure
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon — 4/4.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the continuous effect granting casualty 1 to instants/sorceries."""
        source = self

        # -----------------------------------------------------------------------
        # Continuous effect: grant casualty 1 to instants/sorceries in hand
        # -----------------------------------------------------------------------
        def _apply_casualty_grant(g: "GameState") -> None:
            """Grant casualty 1 to each instant/sorcery in controller's hand."""
            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            # First, clear casualty from all hand instants/sorceries so that
            # when Silverquill is not on the battlefield the cost is removed.
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    if hasattr(card, "casualty"):
                        del card.casualty
            # Check that Silverquill is actually on the battlefield before re-granting
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    card.casualty = 1

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_casualty_grant,
            duration=DURATION_PERMANENT,
        ))
