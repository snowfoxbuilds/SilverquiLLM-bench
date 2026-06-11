"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may
    cast a card for its miracle cost when you draw it if it's the first
    card you drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {"Legendary"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\nAt "
            "the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # ----- Opponent-upkeep loot: may discard a card; if you do, draw.
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _upkeep_effect(game: GameState) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = game.get_hand(ctrl).get_all()
            if not hand:
                return
            try:
                chosen = ctrl.choose_card(
                    hand, "Discard a card to draw a card? (None to decline)"
                )
            except Exception:
                chosen = None
            if chosen is None:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )

        # ----- Miracle {2} for instant/sorcery cards in your hand.
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            # First card drawn this turn (counter is turn-stamped by
            # engine.game.draw_card).
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            types = getattr(event.card, "card_types", set())
            if not types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._miracle_card = event.card
            return True

        def _miracle_effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            # The card must still be in hand to be cast for its miracle cost.
            if not game.get_hand(ctrl).contains(card):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            try:
                wants = ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle "
                    "cost {2}?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            if not ctrl.mana_pool.pay(miracle_cost):
                return
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                # Refund — the cast never happened.
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
