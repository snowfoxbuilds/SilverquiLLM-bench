"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast
    a card for its miracle cost when you draw it if it's the first card you
    drew this turn.)
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
            "miracle {2}. (You may cast a card for its miracle cost when you "
            "draw it if it's the first card you drew this turn.)\nAt the "
            "beginning of each opponent's upkeep, you may discard a card. If "
            "you do, draw a card.",
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

        # --- Miracle {2} on your first-drawn instant/sorcery (card-local) ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if event.player is not ctrl or ctrl is None:
                return False
            if not _on_battlefield(game, source):
                return False
            # Turn-stamped first-draw tracking (cards_drawn_this_turn is never
            # reset by the engine, so track it locally per turn).
            turn = game.turn_number
            if getattr(source, "_miracle_turn", None) != turn:
                source._miracle_turn = turn
                source._miracle_draws = 0
            source._miracle_draws += 1
            if source._miracle_draws != 1:
                return False
            card = event.card
            if card is None or not (
                getattr(card, "card_types", set()) & _INSTANT_SORCERY
            ):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(cost):
                return
            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return
            ctrl.mana_pool.pay(cost)
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except Exception:
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

        # --- Loot at each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or not _on_battlefield(game, source):
                return False
            # An opponent's upkeep = the active player is not the controller.
            return game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand_cards = list(ctrl.zones[Zone.HAND].get_all())
            if not hand_cards:
                return
            try:
                chosen = ctrl.choose_card(
                    hand_cards, "discard a card to draw a card (or decline)"
                )
            except Exception:
                return
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
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
