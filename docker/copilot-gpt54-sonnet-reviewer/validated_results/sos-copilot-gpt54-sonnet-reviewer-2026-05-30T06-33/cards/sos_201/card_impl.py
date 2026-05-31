"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


ORACLE_TEXT = (
    "Flying, haste\n"
    "Each instant and sorcery card in your hand has miracle {2}. "
    "(You may cast a card for its miracle cost when you draw it if it's "
    "the first card you drew this turn.)\n"
    "At the beginning of each opponent's upkeep, you may discard a card. "
    "If you do, draw a card."
)


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("rules_text", ORACLE_TEXT)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def get_granted_miracle_cost(
        self,
        game: "GameState",
        drawn_card: Any,
        player: "Player",
    ) -> ManaCost | None:
        if player is not self.controller:
            return None
        card_types = getattr(drawn_card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        return ManaCost.parse("{2}")

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = self.controller or self.owner
        if controller is None:
            return

        def _condition(_game: "GameState", _event: BeginningOfUpkeepTriggeredEvent) -> bool:
            current_controller = source.controller or source.owner
            return current_controller is not None and _game.active_player is not current_controller

        def _effect(resolving_game: "GameState") -> None:
            from engine.game import discard, draw_card

            current_controller = source.controller or source.owner
            if current_controller is None:
                return

            hand = current_controller.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return

            if not current_controller.choose_yes_no("Discard a card to draw a card?"):
                return

            chosen = current_controller.choose_card(cards_in_hand, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return

            discard(resolving_game, current_controller, chosen)
            draw_card(resolving_game, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
