"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

MIRACLE_COST = "{2}"


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

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # ---- Opponent-upkeep loot: may discard a card; if you do, draw. --
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND].get_all()
            if not hand:
                return
            chosen = ctrl.choose_card(
                hand, "Discard a card to draw a card (or None to decline)"
            )
            if chosen is None or chosen not in hand:
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

        # ---- Miracle {2} on instants/sorceries drawn first this turn. ----
        # Card-local first-draw tracking (turn-stamped); the engine's
        # cards_drawn_this_turn counter is never reset, so it can't be used.
        source._draw_turn_stamp: int = -1
        source._draws_this_turn: int = 0

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            turn = getattr(game, "turn_number", 0)
            if turn != source._draw_turn_stamp:
                source._draw_turn_stamp = turn
                source._draws_this_turn = 0
            source._draws_this_turn += 1
            if source._draws_this_turn != 1:
                return False
            card = event.card
            if not getattr(card, "card_types", set()) & _SPELL_TYPES:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            # The card must still be in hand when the trigger resolves.
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            miracle_cost = ManaCost.parse(MIRACLE_COST)
            if not ctrl.mana_pool.can_pay(miracle_cost, spell=card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {MIRACLE_COST}?"
            ):
                return
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                return  # cast was illegal — card stays in hand, no payment
            ctrl.mana_pool.pay(miracle_cost, spell=card)
            card.mana_spent = miracle_cost.cmc  # paid the miracle cost

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
