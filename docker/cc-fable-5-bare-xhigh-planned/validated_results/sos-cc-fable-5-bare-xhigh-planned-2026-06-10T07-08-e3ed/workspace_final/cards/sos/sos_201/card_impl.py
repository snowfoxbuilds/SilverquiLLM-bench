"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

# Miracle {2}: the alternative cost granted to instant/sorcery cards in
# the controller's hand.
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
        # Stashed by the miracle trigger's condition for its effect.
        self._miracle_card: Any = None

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

        # --- Miracle {2} on instants/sorceries drawn first this turn ---
        # CARD-LOCAL miracle: continuous effects can't reach the hand in
        # this engine, so the grant is modelled as a draw trigger gated to
        # the controller's first draw each turn.

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            # First card drawn this turn (draw_card increments the counter
            # before firing; advance_phase resets it each turn).
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = event.card
            if card is None or not (
                getattr(card, "card_types", set()) & _SPELL_TYPES
            ):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
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
            if not ctrl.mana_pool.can_pay(_MIRACLE_COST):
                return
            ctrl.mana_pool.pay(_MIRACLE_COST)
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                # Refund: the cast was illegal (e.g. no legal target).
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, 2)
                return
            # Record what was actually paid for the miracle cast.
            card.mana_spent = 2

        # --- Loot at the beginning of each opponent's upkeep ---

        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            try:
                chosen = ctrl.choose_card(
                    hand_cards, "Discard a card to draw a card? (None to decline)"
                )
            except Exception:
                chosen = None
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
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
