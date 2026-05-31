"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.triggers import TriggerRegistration

if TYPE_CHECKING:
    from engine.game_state import GameState


_MIRACLE_COST = ManaCost.parse("{2}")


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_from_zone
        from engine.game import discard, draw_card

        source = self
        controller = self.controller or self.owner
        if controller is None:
            return

        def _upkeep_condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            return game.active_player is not controller

        def _upkeep_effect(game: "GameState") -> None:
            hand_cards = game.get_hand(controller).get_all()
            if not hand_cards:
                return
            if not controller.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = controller.choose_card(hand_cards, "Choose a card to discard")
            if chosen not in hand_cards:
                return
            discard(game, controller, chosen)
            draw_card(game, controller)

        def _miracle_condition(game: "GameState", event: DrawsCardTriggeredEvent) -> bool:
            if event.player is not controller:
                return False
            if getattr(controller, "cards_drawn_this_turn", 0) != 1:
                return False
            drawn_card = event.card
            if drawn_card is None:
                return False
            card_types = getattr(drawn_card, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _miracle_stack_factory(
            game: "GameState",
            event: DrawsCardTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> StackObject:
            drawn_card = event.card

            def _miracle_effect(resolving_game: "GameState") -> None:
                if drawn_card is None:
                    return
                if not resolving_game.get_hand(controller).contains(drawn_card):
                    return
                if not controller.choose_yes_no(
                    f"Cast {drawn_card.name} for its miracle cost?"
                ):
                    return
                try:
                    cast_spell_from_zone(
                        resolving_game,
                        controller,
                        drawn_card,
                        Zone.HAND,
                        mana_cost_override=_MIRACLE_COST,
                        ignore_timing=True,
                    )
                except CastingError:
                    return

            return StackObject(
                source=source,
                controller=trigger.controller,
                on_resolve=_miracle_effect,
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
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=lambda _game: None,
                stack_factory=_miracle_stack_factory,
                source=self,
                controller=controller,
            )
        )
