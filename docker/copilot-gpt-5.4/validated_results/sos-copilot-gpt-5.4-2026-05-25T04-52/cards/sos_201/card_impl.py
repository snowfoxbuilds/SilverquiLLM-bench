"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import BeginningOfUpkeepTriggeredEvent
from benchmarks.sos.workspace.engine.game import discard, draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

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
            "Flying, haste\nEach instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_granted_miracle_cost(self, game: GameState, card: Creature) -> ManaCost | None:  # type: ignore[override]
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
        return ManaCost.parse("{2}")

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = source.controller
            return current_controller is not None and game.active_player is not current_controller

        def _effect(game: GameState) -> None:
            current_controller = source.controller
            if current_controller is None:
                return
            hand_cards = list(game.get_hand(current_controller).get_all())
            if not hand_cards:
                return
            if not current_controller.choose_yes_no("Discard a card for Lorehold, the Historian?"):
                return
            chosen_card = current_controller.choose_card(
                hand_cards,
                "Choose a card to discard for Lorehold, the Historian",
            )
            if chosen_card is None or not game.get_hand(current_controller).contains(chosen_card):
                return
            discard(game, current_controller, chosen_card)
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
