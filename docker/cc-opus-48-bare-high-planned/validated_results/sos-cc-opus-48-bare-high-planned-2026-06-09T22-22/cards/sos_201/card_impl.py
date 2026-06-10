"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(obj: Any) -> bool:
    return bool(getattr(obj, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})


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
        # Turn-stamp tracking "your first draw this turn" for miracle.
        self._miracle_turn: int = -1
        self._miracle_card: Any = None

    def _on_battlefield(self, game: "GameState") -> bool:
        ctrl = self.controller
        return ctrl is not None and game.get_battlefield(ctrl).contains(self)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle: first instant/sorcery you draw each turn ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            if not source._on_battlefield(game):
                return False
            if getattr(event, "player", None) is not source.controller:
                return False
            # Is this the controller's first draw this turn? Stamp regardless of
            # card type so later draws this turn are not treated as "first".
            first = source._miracle_turn != game.turn_number
            source._miracle_turn = game.turn_number
            if not first:
                return False
            card = getattr(event, "card", None)
            if not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not game.get_hand(ctrl).contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
            ):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            ctrl.mana_pool.pay(miracle_cost)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        # --- Loot: at the beginning of each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            return source._on_battlefield(game) and game.active_player is not source.controller

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            cards = hand.get_all()
            if not cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

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
