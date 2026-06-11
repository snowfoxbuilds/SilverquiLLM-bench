"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

# Miracle {2} — the cost granted to instant/sorcery cards in hand.
_MIRACLE_GENERIC_COST = 2


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
            "you draw it if it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        self._miracle_card: Any = None

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on instants/sorceries drawn first this turn ---
        # Card-local miracle: continuous effects do not reach the hand, so
        # the granted miracle is modeled as a draw trigger instead.
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            # Engine counter increments before the event fires, so the
            # first draw of the turn sees exactly 1.
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = event.card
            if not getattr(card, "card_types", set()) & {
                CardType.INSTANT,
                CardType.SORCERY,
            }:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            card = source._miracle_card
            source._miracle_card = None
            ctrl = getattr(source, "controller", None)
            if card is None or ctrl is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return  # the card left the hand before the trigger resolved
            cost = ManaCost(generic=_MIRACLE_GENERIC_COST)
            if not ctrl.mana_pool.can_pay(cost, allow_restricted=True):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            ctrl.mana_pool.pay(cost, allow_restricted=True)
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                # Refund — the miracle cast could not legally happen.
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, _MIRACLE_GENERIC_COST)

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
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _loot_effect(game: GameState) -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            chosen = ctrl.choose_card(
                cards_in_hand,
                "You may discard a card to draw a card (None to decline)",
            )
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
