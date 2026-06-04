"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If
    you do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste.\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        self.colors = ["R", "W"]

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        # --- Miracle {2} for instants/sorceries drawn this turn ---
        def _miracle_condition(g: "GameState", event: DrawsCardTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            turn = getattr(g, "turn_number", 0)
            if getattr(source, "_miracle_turn", None) != turn:
                source._miracle_turn = turn
                source._miracle_draws = 0
            source._miracle_draws += 1
            if source._miracle_draws != 1:
                return False
            card = event.card
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            return ctrl.zones[Zone.HAND].contains(card)

        def _miracle_effect(g: "GameState", event: DrawsCardTriggeredEvent) -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.player import ScriptExhaustedError

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            card = event.card
            if card is None or not ctrl.zones[Zone.HAND].contains(card):
                return
            try:
                if not ctrl.choose_yes_no("cast for miracle {2}?"):
                    return
            except (ScriptExhaustedError, NotImplementedError):
                return
            cost = ManaCost.parse("{2}")
            if not ctrl.mana_pool.can_pay(cost):
                return
            ctrl.mana_pool.pay(cost)
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                pass

        # --- Opponent's upkeep: may discard a card, then draw ---
        def _upkeep_condition(
            g: "GameState", event: BeginningOfUpkeepTriggeredEvent
        ) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return g.active_player is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card
            from engine.player import ScriptExhaustedError

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND].get_all()
            if not hand:
                return
            try:
                if not ctrl.choose_yes_no("discard a card to draw a card?"):
                    return
            except (ScriptExhaustedError, NotImplementedError):
                return
            try:
                chosen = ctrl.choose_card(hand, "discard")
            except (ScriptExhaustedError, NotImplementedError):
                chosen = hand[-1]
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
                chosen = hand[-1]
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=self.controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=self.controller,
            )
        )
