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

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self

        # ---- Miracle {2} for your instant/sorcery cards (card-local) ----
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            turn = getattr(game, "turn_number", 0)
            first = getattr(ctrl, "_miracle_first_draw_turn", None) != turn
            if first:
                # Stamp the turn so only the first draw this turn qualifies,
                # regardless of the drawn card's type.
                ctrl._miracle_first_draw_turn = turn
            if not first:
                return False
            card = getattr(event, "card", None)
            if card is None or not (
                getattr(card, "card_types", set()) & _SPELL_TYPES
            ):
                return False
            ctrl._miracle_pending_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            if ctrl is None:
                return
            card = getattr(ctrl, "_miracle_pending_card", None)
            if card is None or not game.get_hand(ctrl).contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            if not ctrl.mana_pool.can_pay(_MIRACLE_COST, instant_or_sorcery=True):
                return
            ctrl.mana_pool.pay(_MIRACLE_COST, instant_or_sorcery=True)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        # ---- Loot on each opponent's upkeep ----
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            return ctrl is not None and game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand_cards = game.get_hand(ctrl).get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(hand_cards, "Discard a card to draw a card?")
            if chosen is None or not game.get_hand(ctrl).contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

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
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
