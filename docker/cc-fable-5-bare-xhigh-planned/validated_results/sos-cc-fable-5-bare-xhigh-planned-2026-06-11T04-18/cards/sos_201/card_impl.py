"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
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
        # Turn-stamped draw counter for "first card you drew this turn".
        # Counting starts when Lorehold is on the battlefield; draws made
        # earlier in the turn (before it entered) are not seen — deliberate
        # limitation.
        self._draw_turn: int = -1
        self._draws_seen: int = 0
        self._miracle_card: Any = None

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self

        # --- Miracle {2} for instants/sorceries on your first draw ---

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            turn = getattr(g, "turn_number", 0)
            if source._draw_turn != turn:
                source._draw_turn = turn
                source._draws_seen = 0
            source._draws_seen += 1
            if source._draws_seen != 1:
                return False
            card = event.card
            if card is None or not (_SPELL_TYPES & getattr(card, "card_types", set())):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.types import ManaType

            ctrl = getattr(source, "controller", None)
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not g.get_hand(ctrl).contains(card):
                return
            try:
                wants = ctrl.choose_yes_no(
                    f"cast {card.name} for its miracle cost {{2}}?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            if not card.can_cast(g):
                return
            if not ctrl.mana_pool.pay(ManaCost(generic=2), spell=card):
                return  # can't pay the miracle cost
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                # Cast failed after payment (e.g. illegal target choice):
                # refund the two mana as {C} (approximation).
                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        # --- Opponent-upkeep loot ---

        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _loot_effect(g: GameState) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = g.get_hand(ctrl).get_all()
            if not hand:
                return
            try:
                chosen = ctrl.choose_card(
                    hand, "discard a card to draw a card (None to decline)"
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in hand:
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        controller = getattr(self, "controller", None) or game.active_player
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
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
