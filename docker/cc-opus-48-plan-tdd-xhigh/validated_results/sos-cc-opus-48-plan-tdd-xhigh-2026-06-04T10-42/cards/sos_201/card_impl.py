"""Card implementation for Lorehold, the Historian (SOS #201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


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
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        self._miracle_card: Any = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Opponent-upkeep loot --------------------------------------
        def _loot_condition(game: Any, event: Any) -> bool:
            return getattr(game, "active_player", None) is not source.controller

        def _loot_effect(game: Any) -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards = list(hand.get_all())
            if not cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards, "card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        # --- Miracle {2} for the first I/S drawn each turn -------------
        def _miracle_condition(game: Any, event: Any) -> bool:
            card = getattr(event, "card", None)
            if card is None:
                return False
            if getattr(event, "player", None) is not source.controller:
                return False
            if not _is_instant_or_sorcery(card):
                return False
            if getattr(event.player, "cards_drawn_this_turn", 0) != 1:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: Any) -> None:
            # ENGINE LIMITATION: miracle modelled as a may-cast for {2} when
            # the first card drawn this turn is an instant/sorcery.
            from engine.casting import cast_spell_free

            ctrl = source.controller
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(card):
                return
            if not ctrl.choose_yes_no("Cast it for its miracle cost {2}?"):
                return
            miracle_cost = ManaCost.parse("{2}")
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            ctrl.mana_pool.pay(miracle_cost)
            cast_spell_free(game, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
