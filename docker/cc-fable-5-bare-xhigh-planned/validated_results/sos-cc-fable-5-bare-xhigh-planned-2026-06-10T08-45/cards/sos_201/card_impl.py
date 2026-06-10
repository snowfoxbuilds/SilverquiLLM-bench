"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
    DrawsCardTriggeredEvent,
)
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


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
        # Turn stamp for "first card you drew this turn" (card-local
        # miracle tracking — draws before this card arrived can't be seen,
        # so the registration turn is conservatively marked as drawn).
        self._miracle_last_turn: int | None = None
        self._miracle_card: Any = None

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player
        self._miracle_last_turn = game.turn_number

        # --- Miracle {2} on instants/sorceries drawn first this turn ---
        def _draw_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            first = g.turn_number != source._miracle_last_turn
            # Any draw consumes "first draw" status for the turn.
            source._miracle_last_turn = g.turn_number
            if not first:
                return False
            if not (_SPELL_TYPES & getattr(event.card, "card_types", set())):
                return False
            source._miracle_card = event.card
            return True

        def _miracle_effect(g: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not g.get_hand(ctrl).contains(card):
                return
            try:
                wants = ctrl.choose_yes_no(
                    f"Cast {card.name} for its miracle cost {{2}}?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            miracle_cost = ManaCost(generic=2)
            # Check payment up front so the cast/pay pair stays atomic.
            if not ctrl.mana_pool.can_pay(miracle_cost, include_restricted=True):
                return
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                return
            # Paying for an instant/sorcery cast: restricted mana is legal.
            ctrl.mana_pool.pay(miracle_cost, include_restricted=True)

        # --- Loot at the beginning of each opponent's upkeep ---
        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _loot_effect(g: GameState) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = g.get_hand(ctrl).get_all()
            if not hand_cards:
                return
            try:
                chosen = ctrl.choose_card(
                    hand_cards, "Discard a card to draw a card? (None declines)"
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in hand_cards:
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
