"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _is_on_battlefield(game: "GameState", obj: Any) -> bool:
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

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Loot: at the beginning of each opponent's upkeep ---
        def _loot_cond(game: Any, event: Any) -> bool:
            return _is_on_battlefield(game, source) and game.active_player is not source.controller

        def _loot_eff(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards = hand.get_all()
            if not cards:
                return
            chosen = ctrl.choose_card(cards, "Discard a card to draw one? (or decline)")
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_cond,
                effect=_loot_eff,
                source=self,
                controller=controller,
            )
        )

        # --- Miracle {2} for instant/sorcery cards in your hand ---
        # Continuous effects don't reach the hand, so this is driven off the
        # draw event with a turn-stamped "first draw seen" marker on the source.
        def _miracle_cond(game: Any, event: Any) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            if getattr(event, "player", None) is not source.controller:
                return False
            # Is this the controller's FIRST draw this turn? Mark it regardless
            # of card type so a later same-turn draw is never treated as first.
            is_first = getattr(source, "_first_draw_turn", None) != game.turn_number
            if is_first:
                source._first_draw_turn = game.turn_number
            if not is_first:
                return False
            card = getattr(event, "card", None)
            if card is None or not (getattr(card, "card_types", set()) & _INSTANT_SORCERY):
                return False
            source._miracle_card = card
            return True

        def _miracle_eff(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            card = getattr(source, "_miracle_card", None)
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return  # can't afford the miracle cost.
            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return
            ctrl.mana_pool.pay(miracle_cost)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_cond,
                effect=_miracle_eff,
                source=self,
                controller=controller,
            )
        )
