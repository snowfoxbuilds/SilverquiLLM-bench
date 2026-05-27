"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import discard, draw_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if it's the first card "
            "you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_granted_miracle_cost(
        self,
        game: "GameState",
        card: Any,
        player: Any | None = None,
    ) -> ManaCost | None:
        """Grant miracle {2} to instant and sorcery cards in your hand."""
        controller = player if player is not None else self.controller
        if controller is None:
            return None
        if not game.get_battlefield(controller).contains(self):
            return None
        if not game.get_hand(controller).contains(card):
            return None
        if not _is_instant_or_sorcery(card):
            return None
        return ManaCost.parse("{2}")

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = self.controller or game.active_player

        def _condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            del event
            ctrl = source.controller
            return ctrl is not None and game.active_player is not ctrl

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            if not cards_in_hand:
                return
            chosen_card = ctrl.choose_card(cards_in_hand, "Choose a card to discard")
            if chosen_card not in cards_in_hand:
                chosen_card = cards_in_hand[0]
            discard(game, ctrl, chosen_card)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
