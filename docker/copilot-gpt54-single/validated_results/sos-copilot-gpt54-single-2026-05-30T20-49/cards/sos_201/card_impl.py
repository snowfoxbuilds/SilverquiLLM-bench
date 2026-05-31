"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.miracle import is_instant_or_sorcery_card, refresh_hand_miracle_grants
from engine.triggers import TriggerRegistration
from engine.types import Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

    _MIRACLE_COST = ManaCost.parse("{2}")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
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

    def granted_miracle_cost_for(self, game: "GameState", card: Any) -> ManaCost | None:
        """Grant miracle {2} to your instant and sorcery cards in hand."""
        _ = game
        if getattr(card, "controller", None) is not self.controller:
            return None
        if not is_instant_or_sorcery_card(card):
            return None
        return self._MIRACLE_COST

    def on_enters_battlefield(self, game: "GameState") -> None:
        refresh_hand_miracle_grants(game, self.controller)

    def on_leaves_battlefield(self, game: "GameState") -> None:
        refresh_hand_miracle_grants(game, self.controller)

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent-upkeep loot trigger."""
        from engine.game import discard, draw_card

        source = self
        controller = self.controller or self.owner or game.active_player

        refresh_hand_miracle_grants(game, controller)

        def _condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            _ = event
            return source.controller is not None and game.active_player is not source.controller

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return

            hand = game.get_hand(ctrl).get_all()
            if not hand:
                return

            chosen = ctrl.choose_card(hand, "Choose a card to discard")
            if chosen is None or not game.get_hand(ctrl).contains(chosen):
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
