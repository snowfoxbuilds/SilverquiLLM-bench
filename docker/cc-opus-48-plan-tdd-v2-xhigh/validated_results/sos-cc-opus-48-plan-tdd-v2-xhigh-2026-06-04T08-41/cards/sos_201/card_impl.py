"""Card implementation for Lorehold, the Historian.

Miracle simplification: real miracle is a special action taken as you draw the
first card of the turn. Here it is modelled as a draw trigger that, for the
controller's first instant/sorcery drawn each turn, offers to pay {2} and cast
it for free from hand. Paying {2} then free-casting approximates the miracle
cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}
_MIRACLE_COST = "{2}"


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Elder Dragon.

    Flying, haste
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
        controller = getattr(self, "controller", None) or game.active_player

        # --- Opponent-upkeep loot ---
        def _loot_condition(g: "GameState", e: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and g.active_player is not ctrl

        def _loot(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards = hand.get_all()
            if not cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards, "Choose a card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        # --- Miracle {2} on first instant/sorcery drawn each turn ---
        def _miracle_condition(g: "GameState", e: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(e, "player", None) is not ctrl:
                return False
            card = getattr(e, "card", None)
            if card is None:
                return False
            if not (getattr(card, "card_types", set()) & _INSTANT_SORCERY):
                return False
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            source._miracle_card = card
            return True

        def _miracle(g: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            ctrl = getattr(source, "controller", None)
            if card is None or ctrl is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'spell')} for miracle {{2}}?"
            ):
                return
            cost = ManaCost.parse(_MIRACLE_COST)
            if not ctrl.mana_pool.can_pay(cost):
                return
            ctrl.mana_pool.pay(cost)
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except CastingError:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle,
                source=self,
                controller=controller,
            )
        )
