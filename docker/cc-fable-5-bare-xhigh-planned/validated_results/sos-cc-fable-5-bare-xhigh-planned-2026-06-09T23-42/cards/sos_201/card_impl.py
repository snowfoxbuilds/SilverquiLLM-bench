"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

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
        # Turn-stamped draw counter for the miracle "first card you drew
        # this turn" check (the engine's cards_drawn_this_turn is never
        # reset per turn). Limitation: draws made before Lorehold entered
        # this turn are not counted.
        self._draw_turn: int = -1
        self._draws_counted: int = 0

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- "At the beginning of each opponent's upkeep, you may discard
        #     a card. If you do, draw a card." ---

        def _upkeep_condition(g: Any, event: Any) -> bool:
            return g.active_player is not getattr(source, "controller", None)

        def _upkeep_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards_in_hand, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Miracle {2} for instant/sorcery cards drawn by you (first
        #     draw of the turn only). Card-local gap: continuous effects
        #     don't reach the hand, so the drawn card is handled directly. ---

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            # Count every draw by the controller (turn-stamped).
            turn = getattr(g, "turn_number", 0)
            if turn != source._draw_turn:
                source._draw_turn = turn
                source._draws_counted = 0
            source._draws_counted += 1
            if source._draws_counted != 1:
                return False
            card = event.card
            if card is None:
                return False
            if not getattr(card, "card_types", set()) & _SPELL_TYPES:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return  # card left hand before the trigger resolved
            if not ctrl.mana_pool.can_pay(_MIRACLE_COST):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            ctrl.mana_pool.pay(_MIRACLE_COST)
            try:
                # Miracle pays {2} instead of the mana cost; the stack path
                # is the free-cast pipeline from hand.
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
