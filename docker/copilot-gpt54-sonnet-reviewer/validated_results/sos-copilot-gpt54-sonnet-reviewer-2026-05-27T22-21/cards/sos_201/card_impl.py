"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import AlternateCost, Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.card import CardImpl


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("colors", {Color.RED, Color.WHITE})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_granted_alternate_costs_for_hand_card(
        self,
        game: "GameState",
        card: "CardImpl",
    ) -> list[AlternateCost]:
        controller = self.controller
        if controller is None:
            return []

        if not controller.zones[Zone.HAND].contains(card):
            return []
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return []
        return [
            AlternateCost(
                name="miracle",
                cost=ManaCost.parse("{2}"),
                source=self,
                ignores_timing=True,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        controller = self.controller or self.owner or game.active_player

        def _condition(current_game: "GameState", _event: BeginningOfUpkeepTriggeredEvent) -> bool:
            return current_game.active_player is not controller

        def _effect(current_game: "GameState") -> None:
            if not controller.choose_yes_no("Discard a card and draw a card?"):
                return
            hand = controller.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            chosen_card = controller.choose_card(cards_in_hand, "discard a card")
            if chosen_card is None or not hand.contains(chosen_card):
                return

            from engine.game import discard, draw_card

            discard(current_game, controller, chosen_card)
            draw_card(current_game, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
