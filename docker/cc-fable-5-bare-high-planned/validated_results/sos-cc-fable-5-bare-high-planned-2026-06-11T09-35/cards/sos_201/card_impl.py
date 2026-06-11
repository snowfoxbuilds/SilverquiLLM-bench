"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may
    cast a card for its miracle cost when you draw it if it's the first
    card you drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.
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
            "miracle {2}.\nAt the beginning of each opponent's upkeep, you "
            "may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Turn-stamped draw tracking for the miracle gate. Deliberate
        # limitation: counts only draws seen while Lorehold's trigger is
        # registered (a draw made before it entered this turn is missed).
        self._draw_turn: int = -1
        self._draws_this_turn: int = 0
        self._miracle_card: Any | None = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on instants/sorceries drawn first this turn ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or event.player is not ctrl:
                return False
            turn = getattr(game, "turn_number", 0)
            if source._draw_turn != turn:
                source._draw_turn = turn
                source._draws_this_turn = 0
            source._draws_this_turn += 1
            if source._draws_this_turn != 1:
                return False  # only the first card drawn this turn
            card_types = getattr(event.card, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._miracle_card = event.card
            return True

        def _miracle_effect(game: "GameState") -> None:
            ctrl = source.controller
            card = source._miracle_card
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not game.get_hand(ctrl).contains(card):
                return  # left hand before the trigger resolved
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            miracle_cost = ManaCost.parse("{2}")
            if not ctrl.mana_pool.pay(miracle_cost, spell=card):
                return  # can't pay — card stays in hand
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, 2)  # refund

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect,
            source=self,
            controller=controller,
        ))

        # --- Loot at the beginning of each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            return ctrl is not None and game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            hand_cards = game.get_hand(ctrl).get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(
                hand_cards, "Discard a card to draw a card? (None to decline)"
            )
            if chosen is None or chosen not in hand_cards:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_loot_condition,
            effect=_loot_effect,
            source=self,
            controller=controller,
        ))
