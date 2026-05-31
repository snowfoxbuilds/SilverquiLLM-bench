"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import AlternativeCastOption, Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import discard, draw_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_controller_battlefield(game: "GameState", permanent: Any) -> bool:
    controller = getattr(permanent, "controller", None)
    if controller is None:
        return False
    return game.get_battlefield(controller).contains(permanent)


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if it's "
            "the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        def _condition(current_game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            del event
            current_controller = self.controller
            return (
                current_controller is not None
                and current_game.active_player is not current_controller
            )

        def _effect(current_game: "GameState") -> None:
            current_controller = self.controller
            if current_controller is None:
                return

            hand = current_game.get_hand(current_controller)
            cards_in_hand = list(hand.get_all())
            if not cards_in_hand:
                return

            if not current_controller.choose_yes_no("Discard a card to draw a card?"):
                return

            chosen_card = current_controller.choose_card(
                cards_in_hand,
                "discard a card",
            )
            if chosen_card is None or not hand.contains(chosen_card):
                return

            discard(current_game, current_controller, chosen_card)
            draw_card(current_game, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_granted_alternative_cast_options(
        self,
        game: "GameState",
        player: Any,
        card: Any,
    ) -> list[AlternativeCastOption]:
        if player is not self.controller:
            return []
        if not _is_on_controller_battlefield(game, self):
            return []
        if not player.zones[Zone.HAND].contains(card):
            return []

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return []

        return [
            AlternativeCastOption(
                name="miracle",
                cost=ManaCost.parse("{2}"),
                source=self,
                description="You may cast this card for its miracle cost.",
                requires_first_draw_this_turn=True,
                ignore_timing=True,
            )
        ]
