"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.  (You may
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
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\nAt "
            "the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Card-local miracle bookkeeping: draws by the controller this
        # turn, counted while this is on the battlefield (deliberate
        # limitation — draws made before it entered are not counted).
        self._draw_turn: int = -1
        self._draw_count: int = 0

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self

        # --- Miracle {2} for instants/sorceries drawn first this turn ---

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or event.player is not ctrl:
                return False
            turn = getattr(g, "turn_number", 0)
            if source._draw_turn != turn:
                source._draw_turn = turn
                source._draw_count = 0
            source._draw_count += 1
            if source._draw_count != 1:
                return False  # only the first card drawn this turn
            card = event.card
            source._miracle_card = card
            return bool(getattr(card, "card_types", set()) & _INSTANT_SORCERY)

        def _miracle_effect(g: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            if ctrl is None:
                return
            card = getattr(source, "_miracle_card", None)
            if card is None or not g.get_hand(ctrl).contains(card):
                return  # no longer in hand — miracle opportunity lost
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.pay(miracle_cost, for_instant_sorcery=True):
                return  # cannot pay {2}
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
                card.mana_spent = 2  # the miracle cost actually paid
            except CastingError:
                # Refund: the cast never happened.  (Approximated as {C}
                # even if colored mana paid the cost.)
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        # --- Loot at the beginning of each opponent's upkeep ---

        def _loot_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            return ctrl is not None and g.active_player is not ctrl

        def _loot_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand_cards = g.get_hand(ctrl).get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(
                hand_cards, "Discard a card to draw a card? (None to decline)"
            )
            if chosen is None or chosen not in hand_cards:
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

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
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
