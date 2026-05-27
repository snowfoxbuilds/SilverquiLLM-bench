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
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def granted_miracle_cost_for(
        self,
        game: GameState,
        player: Any,
        card: Any,
    ) -> ManaCost | None:
        """Grant miracle {2} to instant and sorcery cards in *player*'s hand."""
        if player is not self.controller:
            return None
        if not game.get_hand(player).contains(card):
            return None

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None

        return ManaCost.parse("{2}")

    def register_triggers(self, game: GameState) -> None:
        """Register the opponent-upkeep loot trigger."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, _event: BeginningOfUpkeepTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or game.active_player is ctrl:
                return False
            return game.get_battlefield(ctrl).contains(source)

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            hand = game.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return

            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return

            chosen = ctrl.choose_card(cards_in_hand, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return

            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
