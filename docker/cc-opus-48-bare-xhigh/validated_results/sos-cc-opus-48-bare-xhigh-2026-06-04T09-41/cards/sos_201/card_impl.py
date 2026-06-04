"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


_MIRACLE_COST = "{2}"


def _is_instant_or_sorcery(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
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

        # --- Miracle grant ---------------------------------------------------
        def _miracle_effect(g: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Identify the most-recently-drawn instant/sorcery still in hand.
            card = getattr(self, "_pending_miracle_card", None)
            if card is None or not g.get_hand(controller).contains(card):
                return
            self._cast_for_miracle(g, controller, card)

        # --- Opponent's-upkeep loot -----------------------------------------
        def _loot_condition(g: "GameState", event: Any) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            return g.active_player is not controller

        def _loot_effect(g: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            hand = g.get_hand(controller)
            if len(hand) == 0:
                return
            if not controller.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = controller.choose_card(hand.get_all(), "choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            from engine.game import discard, draw_card

            discard(g, controller, chosen)
            draw_card(g, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=self._make_miracle_condition(source),
                effect=_miracle_effect,
                source=self,
                controller=self.controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=self.controller,
            )
        )

    def _make_miracle_condition(self, source: "LoreholdTheHistorian"):
        def _condition(g: "GameState", event: Any) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None or getattr(event, "player", None) is not controller:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            if getattr(controller, "cards_drawn_this_turn", 0) != 1:
                return False
            if not g.get_hand(controller).contains(card):
                return False
            # Stash the card so the resolving effect knows what to offer.
            source._pending_miracle_card = card
            return True

        return _condition

    def _cast_for_miracle(
        self, game: "GameState", controller: "Player", card: Any
    ) -> None:
        from engine.casting import CastingError, cast_spell

        if not controller.choose_yes_no(
            f"Cast {card.name!r} for its miracle cost {_MIRACLE_COST}?"
        ):
            return
        miracle_cost = ManaCost.parse(_MIRACLE_COST)
        if not controller.mana_pool.can_pay(miracle_cost):
            return
        try:
            cast_spell(
                game,
                controller,
                card,
                alternative_cost=miracle_cost,
                bypass_timing=True,
            )
        except CastingError:
            return
