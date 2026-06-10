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


def _is_instant_or_sorcery(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

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
            "miracle {2}.\nAt the beginning of each opponent's upkeep, you may "
            "discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Turn number on which a draw by the controller was last seen (for the
        # "first card you drew this turn" miracle condition).
        self._miracle_draw_turn: int = -1
        self._miracle_card: Any = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2}: first instant/sorcery you draw each turn ---
        def _miracle_condition(g: "GameState", event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            cur = getattr(g, "turn_number", 0)
            if source._miracle_draw_turn == cur:
                return False  # already had the first draw this turn
            # Mark the first draw this turn (regardless of the card's type, so a
            # non-instant first draw correctly disqualifies later draws).
            source._miracle_draw_turn = cur
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return
            ctrl.mana_pool.pay(miracle_cost)
            from engine.casting import cast_spell_free

            cast_spell_free(g, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Loot: each opponent's upkeep, you may discard then draw ---
        def _loot_condition(g: "GameState", event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and getattr(g, "active_player", None) is not ctrl

        def _loot_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            try:
                chosen = ctrl.choose_card(hand_cards, "discard a card to draw a card")
            except Exception:
                return
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
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
