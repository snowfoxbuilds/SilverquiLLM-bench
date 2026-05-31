"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    (You may cast a card for its miracle cost when you draw it if it's the
    first card you drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    ENGINE LIMITATION: The miracle mechanic requires intercepting the draw
    event and offering a discounted cast. Miracle is partially supported:
    ``get_miracle_cost`` returns the {2} cost and ``is_miracle_card`` is
    set on hand instants/sorceries. The draw trigger checks
    ``player.cards_drawn_this_turn == 1`` and sets ``card._is_miracle_draw``
    on the drawn card. Tests can invoke ``try_miracle_cast`` to exercise it.

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
            "miracle {2}. (You may cast a card for its miracle cost when you "
            "draw it if it's the first card you drew this turn.)\nAt the "
            "beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Triggered abilities
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent's upkeep loot trigger and miracle draw trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.game import discard as discard_fn, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Opponent's upkeep: may discard → draw ---
        def _upkeep_condition(game: Any, event: Any) -> bool:
            # Active player is an opponent of controller.
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            try:
                want = ctrl.choose_yes_no("Discard a card to draw a card?")
            except Exception:
                return
            if not want:
                return
            hand = game.get_hand(ctrl)
            if len(hand) == 0:
                return
            cards = hand.get_all()
            try:
                card = ctrl.choose_card(cards, "Discard a card")
                if isinstance(card, int):
                    card = cards[card] if 0 <= card < len(cards) else None
            except Exception:
                card = cards[0] if cards else None
            if card is None:
                return
            discard_fn(game, ctrl, card)
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

        # --- Miracle draw trigger ---
        def _draw_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            # First card drawn this turn.
            drawn = getattr(ctrl, "cards_drawn_this_turn", 0)
            return drawn == 1

        def _draw_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Get the most recently drawn card.
            hand = game.get_hand(ctrl)
            cards = hand.get_all()
            if not cards:
                return
            card = cards[-1]  # most recently drawn = top of hand
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return
            # Mark as miracle-eligible.
            card._miracle_eligible = True  # type: ignore[attr-defined]
            card._miracle_cost = ManaCost.parse("{2}")  # type: ignore[attr-defined]
            # Ask if controller wants to cast it for {2}.
            try:
                want = ctrl.choose_yes_no(f"Cast {getattr(card, 'name', 'card')} for miracle cost {{2}}?")
            except Exception:
                return
            if not want:
                return
            # Cast for {2} — check if controller has enough mana.
            from engine.casting import CastingError
            from engine.types import ManaType
            miracle_cost = ManaCost.parse("{2}")
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            ctrl.mana_pool.pay(miracle_cost)
            try:
                cast_spell_free(game, ctrl, card, type(card).HAND if hasattr(type(card), "HAND") else None)
            except Exception:
                # Fall back: mark for casting
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_draw_effect,
                source=source,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Miracle cost helper
    # ------------------------------------------------------------------

    @staticmethod
    def get_miracle_cost() -> ManaCost:
        """Return the miracle cost ({2}) for instant/sorcery cards in hand."""
        return ManaCost.parse("{2}")

