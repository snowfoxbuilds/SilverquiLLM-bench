"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_with_alternative_cost
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery card."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


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
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register Lorehold's upkeep and miracle-grant triggers."""
        controller = self.controller
        if controller is None:
            return

        def _opponent_upkeep_condition(
            _game: "GameState",
            _event: BeginningOfUpkeepTriggeredEvent,
        ) -> bool:
            return self.controller is not None and _game.active_player is not self.controller

        def _opponent_upkeep_effect(_game: "GameState") -> None:
            from engine.game import discard, draw_card

            active_controller = self.controller
            if active_controller is None:
                return
            hand = _game.get_hand(active_controller)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            if not active_controller.choose_yes_no(
                "Discard a card to draw a card?"
            ):
                return
            chosen_card = active_controller.choose_card(
                cards_in_hand,
                "Choose a card to discard",
            )
            if chosen_card not in cards_in_hand:
                return
            discard(_game, active_controller, chosen_card)
            draw_card(_game, active_controller)

        def _miracle_condition(
            _game: "GameState",
            event: DrawsCardTriggeredEvent,
        ) -> bool:
            active_controller = self.controller
            if active_controller is None or event.player is not active_controller:
                return False
            if not _is_instant_or_sorcery(event.card):
                return False
            return getattr(event.player, "cards_drawn_this_turn", 0) == 1

        def _miracle_effect(_game: "GameState") -> None:
            active_controller = self.controller
            event = getattr(self, "triggering_event", None)
            drawn_card = getattr(event, "card", None)
            if active_controller is None or drawn_card is None:
                return
            if not _game.get_hand(active_controller).contains(drawn_card):
                return
            miracle_cost = ManaCost.parse("{2}")
            if not active_controller.mana_pool.can_pay(miracle_cost):
                return
            if not active_controller.choose_yes_no(
                f"Cast {drawn_card.name} for its miracle cost?"
            ):
                return
            cast_spell_with_alternative_cost(
                _game,
                active_controller,
                drawn_card,
                Zone.HAND,
                miracle_cost,
                ignore_timing=True,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_opponent_upkeep_condition,
                effect=_opponent_upkeep_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
