"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import CastingError, cast_spell_with_alternative_cost
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.game import discard, draw_card
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState


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
            "(You may cast a card for its miracle cost when you draw it if it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    @staticmethod
    def _is_instant_or_sorcery(card: CardImpl) -> bool:
        return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player
        miracle_cost = ManaCost.parse("{2}")

        def _miracle_condition(game: GameState, event: DrawsCardTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            return source._is_instant_or_sorcery(event.card)

        def _miracle_stack_builder(
            game: GameState,
            event: DrawsCardTriggeredEvent,
        ) -> StackObject | None:
            ctrl = getattr(source, "controller", None)
            drawn_card = event.card
            if ctrl is None or event.player is not ctrl:
                return None
            if not source._is_instant_or_sorcery(drawn_card):
                return None

            def _resolve_trigger(game: GameState) -> None:
                current_controller = getattr(source, "controller", None)
                if current_controller is None:
                    return
                current_hand = game.get_hand(current_controller)
                if not current_hand.contains(drawn_card):
                    return
                if not source._is_instant_or_sorcery(drawn_card):
                    return
                if not current_controller.choose_yes_no(
                    f"Cast {getattr(drawn_card, 'name', 'that card')} for its miracle cost?"
                ):
                    return
                try:
                    cast_spell_with_alternative_cost(
                        game,
                        current_controller,
                        drawn_card,
                        miracle_cost,
                        from_zone=Zone.HAND,
                        ignore_timing=True,
                    )
                except CastingError:
                    return

            return StackObject(
                source=source,
                controller=ctrl,
                targets=[drawn_card],
                on_resolve=_resolve_trigger,
            )

        def _upkeep_condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return game.active_player is not ctrl

        def _upkeep_effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            try:
                chosen = ctrl.choose_card(cards_in_hand, "card to discard")
            except Exception:
                chosen = cards_in_hand[0]
            if chosen not in cards_in_hand:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=lambda game: None,
                source=self,
                controller=controller,
                stack_builder=_miracle_stack_builder,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )
