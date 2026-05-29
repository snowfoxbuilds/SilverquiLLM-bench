"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    MIRACLE_COST = ManaCost.parse("{2}")

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
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if it's the first card "
            "you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_granted_miracle_cost(
        self,
        game: GameState,
        card: Any,
    ) -> ManaCost | None:
        controller = self.controller
        if controller is None:
            return None
        if not game.get_battlefield(controller).contains(self):
            return None
        if not game.get_hand(controller).contains(card):
            return None

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None

        return self.MIRACLE_COST

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return False
            if not game.get_battlefield(current_controller).contains(source):
                return False
            return game.active_player is not current_controller

        def _effect(game: GameState) -> None:
            from engine.game import discard, draw_card

            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return

            hand = game.get_hand(current_controller)
            hand_cards = hand.get_all()
            if not hand_cards:
                return
            if not current_controller.choose_yes_no(
                "Discard a card to draw a card?"
            ):
                return

            chosen_card = current_controller.choose_card(
                hand_cards,
                "card to discard for Lorehold, the Historian",
            )
            if chosen_card not in hand_cards or not hand.contains(chosen_card):
                return

            discard(game, current_controller, chosen_card)
            if not hand.contains(chosen_card):
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
