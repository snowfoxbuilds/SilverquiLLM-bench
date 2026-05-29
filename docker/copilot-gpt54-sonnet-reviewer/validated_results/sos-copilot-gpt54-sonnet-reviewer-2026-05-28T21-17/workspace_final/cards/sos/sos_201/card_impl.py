"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if it's the first card "
            "you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def miracle_cost_for(self, game: "GameState", player: Any, card: Any) -> ManaCost | None:
        """Grant miracle {2} to instant and sorcery cards drawn by this card's controller."""
        from engine.types import CardType

        if player is not self.controller:
            return None
        if not self._is_on_battlefield(game):
            return None
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        return ManaCost.parse("{2}")

    def register_triggers(self, game: "GameState") -> None:
        """Register the upkeep loot trigger."""
        source = self
        controller = self.controller
        if controller is None:
            return

        def _condition(current_game: "GameState", _event: BeginningOfUpkeepTriggeredEvent) -> bool:
            return (
                source._is_on_battlefield(current_game)
                and current_game.active_player is not controller
            )

        def _effect(current_game: "GameState") -> None:
            from engine.game import discard, draw_card
            from engine.types import Zone

            hand = controller.zones[Zone.HAND]
            if len(hand) == 0:
                return
            if not controller.choose_yes_no("Discard a card to draw a card?"):
                return

            cards_in_hand = hand.get_all()
            chosen = controller.choose_card(cards_in_hand, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return

            discard(current_game, controller, chosen)
            draw_card(current_game, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _is_on_battlefield(self, game: "GameState") -> bool:
        controller = self.controller
        if controller is not None and game.get_battlefield(controller).contains(self):
            return True
        return any(game.get_battlefield(player).contains(self) for player in game.players)
