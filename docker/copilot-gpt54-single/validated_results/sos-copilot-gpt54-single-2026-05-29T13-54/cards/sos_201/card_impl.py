"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import AlternateCastPermission, Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


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
        """Register Lorehold's opponent-upkeep loot trigger."""
        from engine.game import discard, draw_card

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = game.get_hand(ctrl).get_all()
            if not hand_cards:
                return
            if not ctrl.choose_yes_no("Discard a card, then draw a card?"):
                return
            chosen = ctrl.choose_card(hand_cards, "card to discard")
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

    def on_card_drawn(
        self,
        game: "GameState",
        player: "Player",
        card: Any,
        draw_number_this_turn: int,
    ) -> None:
        """Grant a public miracle window to the first instant/sorcery drawn each turn."""
        if player is not getattr(self, "controller", None):
            return
        if draw_number_this_turn != 1:
            return
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        card.grant_alternate_cast_permission(
            AlternateCastPermission(
                label="miracle",
                mana_cost=ManaCost.parse("{2}"),
                from_zone=Zone.HAND,
                granted_by=self,
                ignore_timing=True,
                expires="draw_window",
            )
        )
