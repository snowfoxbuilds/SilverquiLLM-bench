"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_MANA_COST = ManaCost(generic=3, pips={ManaType.RED: 1, ManaType.WHITE: 1})


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", _MANA_COST)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}. (You may cast a card for its miracle cost when you "
            "draw it if it's the first card you drew this turn.)\nAt the "
            "beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle draw trigger and opponent-upkeep loot trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle trigger ---
        _last_turn: list[int] = [-1]
        _draws_this_turn: list[int] = [0]
        _miracle_card: list[Any] = [None]

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            # Turn-stamp tracking: count ALL draws by controller this turn.
            current_turn = g.turn_number
            if _last_turn[0] != current_turn:
                _last_turn[0] = current_turn
                _draws_this_turn[0] = 0
            _draws_this_turn[0] += 1
            if _draws_this_turn[0] != 1:
                return False
            drawn_card = event.card
            if drawn_card is None:
                return False
            is_is = (
                CardType.INSTANT in getattr(drawn_card, "card_types", set())
                or CardType.SORCERY in getattr(drawn_card, "card_types", set())
            )
            if is_is:
                _miracle_card[0] = drawn_card
            return is_is

        def _miracle_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            card = _miracle_card[0]
            _miracle_card[0] = None
            if card is None or not g.get_hand(ctrl).contains(card):
                return
            try:
                if not ctrl.choose_yes_no(f"Cast {getattr(card, 'name', 'card')} for miracle {2}?"):
                    return
            except Exception:
                return
            # Deduct {2} and cast for free from hand.
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            ctrl.mana_pool.pay(miracle_cost)
            from engine.casting import cast_spell_free
            try:
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except Exception:
                # Refund {2} on failure to cast
                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Opponent upkeep: may discard to draw ---
        def _loot_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Must be an opponent's upkeep, not our own.
            return g.active_player is not ctrl

        def _loot_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = list(g.get_hand(ctrl).get_all())
            if not hand:
                return
            try:
                if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                    return
                chosen = ctrl.choose_card(hand, "Choose a card to discard")
            except Exception:
                return
            if chosen is None:
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
