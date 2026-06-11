"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

MIRACLE_COST = ManaCost(generic=2)


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.  (You may
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
        # Turn number of the controller's last seen draw — used to detect
        # "first card drawn this turn" (card-local miracle tracking).
        self._seen_draw_turn: int = -1

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} for instant/sorcery cards drawn first this turn ---

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            # Track *every* draw by the controller, so later draws this
            # turn are never "first" even if the first didn't match.
            turn = getattr(g, "turn_number", 0)
            is_first = turn != source._seen_draw_turn
            source._seen_draw_turn = turn
            if not is_first:
                return False
            card = getattr(event, "card", None)
            if card is None:
                return False
            if not getattr(card, "card_types", set()) & _SPELL_TYPES:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            card = getattr(source, "_miracle_card", None)
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return  # left hand before the trigger resolved
            if not ctrl.mana_pool.can_pay(MIRACLE_COST, spell=card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            ctrl.mana_pool.pay(MIRACLE_COST, spell=card)
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Opponent-upkeep loot ---

        def _loot_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            return ctrl is not None and g.active_player is not ctrl

        def _loot_effect(g: GameState) -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            chosen = ctrl.choose_card(
                cards_in_hand, "Discard a card to draw a card? (None to decline)"
            )
            if chosen is None or not hand.contains(chosen):
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
