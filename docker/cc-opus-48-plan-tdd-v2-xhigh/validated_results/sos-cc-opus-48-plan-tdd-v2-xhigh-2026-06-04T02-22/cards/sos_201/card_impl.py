"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.  (You may
    cast a card for its miracle cost when you draw it if it's the first card
    you drew this turn.)
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
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. (You "
            "may cast a card for its miracle cost when you draw it if it's the "
            "first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
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

        # --- Miracle grant: cast the first instant/sorcery you draw for {2} ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            if not game.get_battlefield(ctrl).contains(source):
                return False
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            if not game.get_hand(ctrl).contains(card):
                return False
            _miracle_condition._last_card = card  # type: ignore[attr-defined]
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_for_cost

            ctrl = getattr(source, "controller", None)
            card = getattr(_miracle_condition, "_last_card", None)
            if ctrl is None or card is None:
                return
            if not game.get_hand(ctrl).contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
            ):
                return
            cast_for_cost(game, ctrl, card, ManaCost.parse("{2}"))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Loot at the beginning of each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if not game.get_battlefield(ctrl).contains(source):
                return False
            return game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            cards = hand.get_all()
            if not cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards, "Choose a card to discard")
            if chosen is None:
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
