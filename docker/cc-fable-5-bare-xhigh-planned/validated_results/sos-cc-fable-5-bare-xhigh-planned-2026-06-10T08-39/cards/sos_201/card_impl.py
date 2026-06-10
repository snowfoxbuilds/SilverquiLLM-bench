"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

_MIRACLE_COST_GENERIC = 2  # miracle {2}


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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
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
        self._miracle_card: Any | None = None

    def register_triggers(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration
        from engine.types import ManaCost as _ManaCost

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on instant/sorcery cards drawn first this turn ---

        def _miracle_condition(g: GameState, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            # draw_card increments the counter before firing, so the first
            # draw of the turn shows exactly 1.
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = getattr(event, "card", None)
            if card is None or not (_SPELL_TYPES & getattr(card, "card_types", set())):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(g: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return  # no longer in hand — miracle window gone
            try:
                wants = ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                )
            except Exception:
                return
            if not wants:
                return
            if not card.can_cast(g):
                return
            miracle_cost = _ManaCost(generic=_MIRACLE_COST_GENERIC)
            if not ctrl.mana_pool.can_pay(miracle_cost, for_instant_sorcery=True):
                return
            ctrl.mana_pool.pay(miracle_cost, for_instant_sorcery=True)
            try:
                # Deduct the miracle cost above, then use the free-cast
                # stack path (the engine has no pay-alternative-cost cast).
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

        # --- At the beginning of each opponent's upkeep: loot 1 ---

        def _upkeep_condition(g: GameState, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _upkeep_effect(g: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            try:
                chosen = ctrl.choose_card(
                    cards_in_hand,
                    "You may discard a card to draw a card (None to decline)",
                )
            except Exception:
                return
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
