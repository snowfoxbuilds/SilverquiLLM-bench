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
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon, 5/5.

    Flying, Haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    MIRACLE_COST = ManaCost.parse("{2}")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault(
            "rules_text",
            "Flying, Haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)
        self.miracle_cost: ManaCost = self.MIRACLE_COST

    # ------------------------------------------------------------------
    # Miracle mechanic
    # ------------------------------------------------------------------

    def is_miracle_eligible(self, card: Any) -> bool:
        """Return True if the card is an instant or sorcery (eligible for miracle {2})."""
        card_types = getattr(card, "card_types", set())
        return CardType.INSTANT in card_types or CardType.SORCERY in card_types

    def grant_miracle_to_hand(self, game: "GameState") -> None:
        """Set miracle_cost = {2} on each instant/sorcery in the controller's hand.

        This implements the continuous effect: "Each instant and sorcery card
        in your hand has miracle {2}." Called on ETB and can be called each
        turn to keep the effect current.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        hand = controller.zones.get(Zone.HAND)
        if hand is None:
            return
        for card in hand.get_all():
            if self.is_miracle_eligible(card):
                card.miracle_cost = self.MIRACLE_COST

    def on_resolve(self, game: "GameState") -> None:
        """When Lorehold enters the battlefield, apply miracle to hand."""
        self.grant_miracle_to_hand(game)

    # ------------------------------------------------------------------
    # Triggered ability — opponent's upkeep loot
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the upkeep loot trigger."""
        source = self
        controller = self.controller

        def _condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            # Fire only on an opponent's upkeep
            current_controller = getattr(source, "controller", controller)
            return game.active_player is not current_controller

        def _effect(game: "GameState") -> None:
            current_controller = getattr(source, "controller", controller)
            if current_controller is None:
                return

            wants_to_discard = current_controller.choose_yes_no(
                "You may discard a card. If you do, draw a card."
            )
            if not wants_to_discard:
                return

            hand = current_controller.zones[Zone.HAND]
            hand_cards = hand.get_all()
            if not hand_cards:
                return

            to_discard = current_controller.choose_card(hand_cards, "Choose a card to discard")

            # Validate the chosen card is actually still in hand (guard against
            # stale choices) before attempting to discard.
            if to_discard is None or not hand.contains(to_discard):
                return

            from engine.game import discard, draw_card
            discard(game, current_controller, to_discard)

            # "If you do" — only draw if the discard succeeded (card moved to graveyard).
            graveyard = current_controller.zones[Zone.GRAVEYARD]
            if graveyard.contains(to_discard):
                draw_card(game, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
