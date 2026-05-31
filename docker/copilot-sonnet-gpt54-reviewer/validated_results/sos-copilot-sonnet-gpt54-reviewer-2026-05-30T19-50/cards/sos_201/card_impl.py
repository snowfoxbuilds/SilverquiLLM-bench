"""Card implementation for Lorehold, the Historian (SOS #201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast
    a card for its miracle cost when you draw it if it's the first card you
    drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card. If
    you do, draw a card.

    SOS collector number 201.
    """

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
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def _is_on_battlefield(self, game: "GameState") -> bool:
        """Return True if this creature is on the battlefield."""
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(self):
                return True
        return False

    def register_triggers(self, game: "GameState") -> None:
        """Register the miracle-grant draw trigger and opponent upkeep trigger."""
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # ------------------------------------------------------------------
        # 1. Miracle-grant trigger: fires when controller draws first card
        # ------------------------------------------------------------------
        def _miracle_condition(game: "GameState", event: Any) -> bool:
            if event.player is not controller:
                return False
            if not source._is_on_battlefield(game):
                return False
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Must be the first card drawn this turn
            drawn = getattr(event.player, "cards_drawn_this_turn", 0)
            return drawn == 1

        def _miracle_effect(game: "GameState") -> None:
            from engine.player import ScriptExhaustedError

            hand = game.get_hand(controller)
            candidates = [
                c for c in hand.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # Apply miracle to the most recently drawn instant/sorcery
            drawn_card = candidates[-1]

            try:
                want_cast = controller.choose_yes_no(
                    f"Cast {getattr(drawn_card, 'name', 'card')} for its miracle cost {{2}}?"
                )
            except ScriptExhaustedError:
                want_cast = False

            if not want_cast:
                return

            miracle_cost = ManaCost.parse("{2}")
            if not controller.mana_pool.can_pay(miracle_cost):
                return

            controller.mana_pool.pay(miracle_cost)

            from engine.casting import cast_spell_free

            try:
                cast_spell_free(game, controller, drawn_card, Zone.HAND)
            except Exception:
                # Refund if cast failed
                from engine.types import ManaType
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=source,
                controller=controller,
            )
        )

        # ------------------------------------------------------------------
        # 2. Opponent upkeep trigger: discard → draw
        # ------------------------------------------------------------------
        def _upkeep_condition(game: "GameState", event: Any) -> bool:
            return game.active_player is not controller

        def _upkeep_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card
            from engine.player import ScriptExhaustedError

            hand = game.get_hand(controller)
            cards_in_hand = list(hand.get_all())
            if not cards_in_hand:
                return

            try:
                want_discard = controller.choose_yes_no(
                    "Discard a card? (If you do, draw a card.)"
                )
            except ScriptExhaustedError:
                want_discard = False

            if not want_discard:
                return

            try:
                chosen = controller.choose(
                    cards_in_hand,
                    "Choose a card to discard.",
                )
            except ScriptExhaustedError:
                chosen = cards_in_hand[0]

            if chosen is None:
                return

            discard(game, controller, chosen)
            draw_card(game, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=source,
                controller=controller,
            )
        )
