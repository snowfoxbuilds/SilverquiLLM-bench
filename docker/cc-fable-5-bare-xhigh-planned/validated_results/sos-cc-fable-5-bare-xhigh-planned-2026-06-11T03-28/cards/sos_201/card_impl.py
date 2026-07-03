"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_OR_SORCERY = {CardType.INSTANT, CardType.SORCERY}
_MIRACLE_COST = ManaCost(generic=2)


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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
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
        # Turn-stamped draw tracking for miracle (card-local — the engine
        # never resets players' cards_drawn_this_turn).
        self._draw_turn: int | None = None
        self._draws_this_turn: int = 0
        self._miracle_card: Any | None = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} for instant/sorcery cards you draw first ---

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            turn = g.turn_number
            if source._draw_turn != turn:
                source._draw_turn = turn
                source._draws_this_turn = 0
            source._draws_this_turn += 1
            if source._draws_this_turn != 1:
                return False
            drawn = event.card
            if not getattr(drawn, "card_types", set()) & _INSTANT_OR_SORCERY:
                return False
            source._miracle_card = drawn
            return True

        def _miracle_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            drawn = source._miracle_card
            source._miracle_card = None
            if ctrl is None or drawn is None:
                return
            if not ctrl.zones[Zone.HAND].contains(drawn):
                return  # the card left the hand before the trigger resolved
            if not ctrl.mana_pool.can_pay(_MIRACLE_COST, for_instant_sorcery=True):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(drawn, 'name', 'card')} for its miracle cost {{2}}?"
            ):
                return
            if not ctrl.mana_pool.pay(_MIRACLE_COST, for_instant_sorcery=True):
                return
            try:
                cast_spell_free(g, ctrl, drawn, Zone.HAND)
            except CastingError:
                pass  # cast turned out illegal — the card stays in hand

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect,
            source=self,
            controller=controller,
        ))

        # --- At the beginning of each opponent's upkeep: loot ---

        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            cards_in_hand = ctrl.zones[Zone.HAND].get_all()
            if not cards_in_hand:
                return
            chosen = ctrl.choose_card(
                cards_in_hand, "Discard a card to draw a card? (None to decline)"
            )
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_upkeep_condition,
            effect=_upkeep_effect,
            source=self,
            controller=controller,
        ))
