"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian -- {3}{R}{W} -- 5/5 Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword(0))
        kwargs["keywords"] = kwargs["keywords"] | Keyword.FLYING | Keyword.HASTE
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        """Register the upkeep looting trigger and miracle-related abilities."""
        controller = self.controller

        # --- Grant miracle {2} to instants/sorceries in controller's hand ---
        self._apply_miracle_to_hand(game)

        # --- Miracle draw trigger: watch for first card drawn each turn ---
        lorehold = self

        def _miracle_draw_condition(game: GameState, event: DrawsCardTriggeredEvent) -> bool:
            """Only trigger on the first card drawn this turn by the controller,
            and only if the drawn card is an instant or sorcery."""
            if event.player is not controller:
                return False
            drawn = event.card
            if drawn is None:
                return False
            card_types = getattr(drawn, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Check if this is the first card drawn this turn
            cards_drawn = getattr(event.player, "cards_drawn_this_turn", 0)
            return cards_drawn == 1

        def _miracle_draw_effect(game: GameState) -> None:
            """Mark the drawn card as miracle-revealed so it can be cast for {2}."""
            # Find the most recently drawn instant/sorcery in controller's hand
            hand = game.get_hand(controller)
            hand_cards = hand.get_all()
            for card in reversed(hand_cards):
                card_types = getattr(card, "card_types", set())
                if (CardType.INSTANT in card_types or CardType.SORCERY in card_types):
                    if not getattr(card, "_miracle_revealed", False):
                        card._miracle_revealed = True
                        card.miracle_triggered = True
                        # Set miracle cost if not already set
                        if not hasattr(card, "miracle_cost") or card.miracle_cost is None:
                            card.miracle_cost = ManaCost.parse("{2}")
                        break

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_draw_condition,
            effect=_miracle_draw_effect,
            source=lorehold,
            controller=controller,
        ))

        # --- Upkeep looting trigger ---
        def _upkeep_condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            """Only trigger during an opponent's upkeep (not controller's)."""
            active = game.active_player
            return active is not controller

        def _upkeep_effect(game: GameState) -> None:
            """May discard a card; if you do, draw a card."""
            from engine.game import draw_card, discard

            # Ask the controller if they want to discard
            may_discard = controller.choose_yes_no(
                "Lorehold, the Historian: discard a card to draw a card?"
            )
            if not may_discard:
                return

            # Check if controller has cards in hand to discard
            hand = game.get_hand(controller)
            hand_cards = hand.get_all()
            if not hand_cards:
                return  # No cards to discard, do nothing

            # Choose a card to discard (first card for deterministic behavior)
            if len(hand_cards) == 1:
                chosen = hand_cards[0]
            else:
                chosen = controller.choose_card(
                    hand_cards, "Choose a card to discard"
                )
                if chosen is None:
                    chosen = hand_cards[0]

            # Discard the chosen card
            discard(game, controller, chosen)

            # Draw a card
            draw_card(game, controller)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_upkeep_condition,
            effect=_upkeep_effect,
            source=lorehold,
            controller=controller,
        ))

    def _apply_miracle_to_hand(self, game: GameState) -> None:
        """Apply miracle {2} to all instants and sorceries in controller's hand."""
        controller = self.controller
        if controller is None:
            return

        hand = game.get_hand(controller)
        miracle_cost = ManaCost.parse("{2}")

        for card in hand.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                card.miracle_cost = miracle_cost
