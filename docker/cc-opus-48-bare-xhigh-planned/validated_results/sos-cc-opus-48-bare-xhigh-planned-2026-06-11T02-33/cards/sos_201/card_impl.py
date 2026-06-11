"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


def _on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


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
        # Turn number on which the controller already had their first draw.
        self._miracle_turn: int | None = None
        self._miracle_card: Any = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on the first instant/sorcery you draw each turn ---
        def _miracle_cond(g: Any, ev: Any) -> bool:
            if not _on_battlefield(g, source):
                return False
            if getattr(ev, "player", None) is not source.controller:
                return False
            turn = g.turn_number
            if source._miracle_turn == turn:
                return False  # not your first draw this turn
            source._miracle_turn = turn  # this draw is your first this turn
            card = getattr(ev, "card", None)
            if card is None or not (getattr(card, "card_types", set()) & _SPELL_TYPES):
                return False
            source._miracle_card = card
            return True

        def _miracle_eff(g: "GameState") -> None:
            card = source._miracle_card
            source._miracle_card = None
            controller_ = source.controller
            if card is None or controller_ is None:
                return
            if not controller_.zones[Zone.HAND].contains(card):
                return
            miracle_cost = ManaCost(generic=2)
            if not controller_.mana_pool.can_pay(miracle_cost):
                return
            if not controller_.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            controller_.mana_pool.pay(miracle_cost)
            from engine.casting import cast_spell_free
            try:
                cast_spell_free(g, controller_, card, Zone.HAND)
            except Exception:
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_cond,
            effect=_miracle_eff,
            source=self,
            controller=controller,
        ))

        # --- Loot at the beginning of each opponent's upkeep ---
        def _loot_cond(g: Any, ev: Any) -> bool:
            return _on_battlefield(g, source) and g.active_player is not source.controller

        def _loot_eff(g: "GameState") -> None:
            controller_ = source.controller
            if controller_ is None:
                return
            hand_cards = controller_.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            chosen = controller_.choose_card(hand_cards, "discard a card to draw a card")
            if chosen is None or not controller_.zones[Zone.HAND].contains(chosen):
                return
            from engine.game import discard, draw_card
            discard(g, controller_, chosen)
            draw_card(g, controller_)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_loot_cond,
            effect=_loot_eff,
            source=self,
            controller=controller,
        ))
