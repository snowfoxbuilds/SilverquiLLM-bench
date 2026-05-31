"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import discard, draw_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs["keywords"] = (kwargs.get("keywords") or Keyword(0)) | Keyword.FLYING | Keyword.HASTE
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)
        self.mechanic_keywords: set[str] = {"Miracle"}
        self.keyword_metadata: dict[str, dict[str, Any]] = {
            "Miracle": {"cost": ManaCost.parse("{2}")},
        }

    def get_miracle_cost_for(
        self,
        game: "GameState",
        player: "Player",
        card: Any,
    ) -> ManaCost | None:
        """Grant miracle {2} to instant and sorcery cards in your hand."""
        if player is not self.controller:
            return None
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        return self.keyword_metadata["Miracle"]["cost"]

    def register_triggers(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        def _condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            return game.active_player is not controller

        def _effect(game: "GameState") -> None:
            hand = game.get_hand(controller)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            if not controller.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = controller.choose_card(cards_in_hand, "card to discard")
            if chosen is None or not hand.contains(chosen):
                chosen = cards_in_hand[-1]
            discard(game, controller, chosen)
            draw_card(game, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
