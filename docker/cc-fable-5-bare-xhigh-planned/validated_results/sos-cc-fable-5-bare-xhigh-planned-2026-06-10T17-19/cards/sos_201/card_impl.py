"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon 5/5.

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
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\nAt "
            "the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on instants/sorceries drawn first this turn ---
        # Card-local miracle: no general miracle subsystem.  Continuous
        # effects can't reach the hand, so the drawn card is handled here.

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False  # only the first card drawn this turn
            card = event.card
            if not getattr(card, "card_types", set()) & _SPELL_TYPES:
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return  # the card left the hand before the trigger resolved
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost, spell=card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for its miracle "
                "cost {2}?"
            ):
                return
            if not card.can_cast(game):
                return
            if not ctrl.mana_pool.pay(miracle_cost, spell=card):
                return
            try:
                # Miracle cost was paid above; the free-cast path puts the
                # spell on the stack from hand without further payment.
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except Exception:
                pass  # cast failed after payment (e.g. bad target choice)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Opponent-upkeep loot ---

        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(
                hand_cards, "Discard a card to draw a card (None to decline)"
            )
            if chosen is None or chosen not in hand_cards:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )
