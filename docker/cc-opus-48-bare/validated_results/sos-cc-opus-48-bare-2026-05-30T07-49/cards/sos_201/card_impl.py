"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.  Each instant and sorcery card in your hand has miracle
    {2}.  At the beginning of each opponent's upkeep, you may discard a card.
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
            "miracle {2}.\nAt the beginning of each opponent's upkeep, you may "
            "discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # LIFO stash of drawn cards awaiting their miracle trigger.
        self._miracle_pending: list[Any] = []

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        # --- Miracle {2} on the first instant/sorcery drawn each turn ---
        def _miracle_condition(g: "GameState", event: Any) -> bool:
            if not _is_on_battlefield(g, source):
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(event, "player", None) is not controller:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            if getattr(controller, "cards_drawn_this_turn", 0) != 1:
                return False
            source._miracle_pending.append(card)
            return True

        def _miracle_effect(g: "GameState") -> None:
            source._resolve_miracle(g)

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

        # --- Each opponent's upkeep: loot 1 (discard a card, draw a card) ---
        def _loot_condition(g: "GameState", event: Any) -> bool:
            if not _is_on_battlefield(g, source):
                return False
            ctrl = source.controller
            if ctrl is None:
                return False
            return g.active_player is not ctrl

        def _loot_effect(g: "GameState") -> None:
            source._resolve_loot(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )

    def _resolve_miracle(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free

        if not self._miracle_pending:
            return
        card = self._miracle_pending.pop()

        controller = self.controller
        if controller is None:
            return
        if not game.get_hand(controller).contains(card):
            return

        cost = ManaCost(generic=2)
        if not controller.mana_pool.can_pay(cost):
            return
        if not controller.choose_yes_no(
            f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
        ):
            return

        controller.mana_pool.pay(cost)
        cast_spell_free(game, controller, card, Zone.HAND)

    def _resolve_loot(self, game: "GameState") -> None:
        from engine.game import discard, draw_card

        controller = self.controller
        if controller is None:
            return
        hand = list(game.get_hand(controller).get_all())
        if not hand:
            return
        if not controller.choose_yes_no("Discard a card to draw a card?"):
            return
        chosen = controller.choose_card(hand, "card to discard")
        if chosen is None or not game.get_hand(controller).contains(chosen):
            return
        discard(game, controller, chosen)
        draw_card(game, controller)
