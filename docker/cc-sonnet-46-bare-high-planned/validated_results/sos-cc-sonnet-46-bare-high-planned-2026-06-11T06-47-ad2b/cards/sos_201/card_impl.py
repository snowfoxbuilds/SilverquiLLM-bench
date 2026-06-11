"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
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
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. (You may "
            "cast a card for its miracle cost when you draw it if it's the first card "
            "you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle draw trigger and opponent-upkeep loot trigger."""
        from engine.casting import CastingError, cast_spell_free
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} trigger ---
        # Track the first draw per (player, turn_number) so we can detect the
        # first draw of each turn without an engine-level counter reset.
        _first_draw_turn: dict = {}
        _miracle_queue: deque = deque()

        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            current_turn = game.turn_number
            player_id = id(ctrl)
            if _first_draw_turn.get(player_id) == current_turn:
                return False  # Not the first draw this turn
            # Mark this as the first draw of the current turn
            _first_draw_turn[player_id] = current_turn
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            is_inst_sorc = CardType.INSTANT in card_types or CardType.SORCERY in card_types
            if is_inst_sorc:
                _miracle_queue.append(card)
            return is_inst_sorc

        def _miracle_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _miracle_queue:
                return
            card = _miracle_queue.popleft()
            if not game.get_hand(ctrl).contains(card):
                return
            try:
                cast_it = ctrl.choose_yes_no(f"Cast {card.name} for miracle {{2}}?")
            except Exception:
                cast_it = False
            if not cast_it:
                return
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=source,
                controller=controller,
            )
        )

        # --- Opponent's upkeep loot trigger ---
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            hand_cards = hand.get_all()
            if not hand_cards:
                return
            try:
                discard_it = ctrl.choose_yes_no("Discard a card to draw a card?")
            except Exception:
                discard_it = False
            if not discard_it:
                return
            try:
                to_discard = ctrl.choose_card(hand_cards, "choose card to discard")
            except Exception:
                to_discard = hand_cards[-1]
            if to_discard is not None and hand.contains(to_discard):
                discard(game, ctrl, to_discard)
                draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=source,
                controller=controller,
            )
        )
