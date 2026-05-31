"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def grant_miracle_to_hand(self, game: "GameState") -> None:
        """Grant miracle {2} to all instant and sorcery cards in controller's hand."""
        controller = self.controller
        if controller is None:
            return
        hand = controller.zones[Zone.HAND].get_all()
        miracle_cost = ManaCost.parse("{2}")
        for card in hand:
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                card.has_miracle = True
                card.miracle_cost = miracle_cost

    def on_opponent_upkeep(self, game: "GameState") -> None:
        """Discard a card to draw a card (opponent's upkeep trigger effect)."""
        from engine.game import discard, draw_card

        controller = self.controller
        if controller is None:
            return
        hand = controller.zones[Zone.HAND].get_all()
        if hand:
            # Discard the first card in hand (deterministic for test; full impl uses choice).
            discard(game, controller, hand[0])
            draw_card(game, controller)

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent upkeep trigger."""
        source = self

        def _condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Fire during any upkeep (simplified — in full impl, check active player is opponent).
            # The active player is the opponent if they're not the controller.
            active = game.active_player
            return active is not controller

        def _effect(game: "GameState") -> None:
            source.on_opponent_upkeep(game)
            source.grant_miracle_to_hand(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )
