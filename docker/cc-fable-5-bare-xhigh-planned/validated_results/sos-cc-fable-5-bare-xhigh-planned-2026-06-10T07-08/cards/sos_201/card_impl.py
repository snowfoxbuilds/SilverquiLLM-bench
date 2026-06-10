"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Drawn cards whose miracle window is pending (LIFO — matches
        # trigger resolution order off the stack).
        self._pending_miracles: list[Any] = []

    def register_triggers(self, game: GameState) -> None:
        self._register_miracle(game)
        self._register_upkeep_loot(game)

    # ------------------------------------------------------------------
    # Miracle {2} for instants/sorceries drawn first this turn
    # ------------------------------------------------------------------

    def _register_miracle(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            # First card drawn this turn (draw_card increments the counter
            # before firing the event; the engine resets it each turn).
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = event.card
            if not (_SPELL_TYPES & getattr(card, "card_types", set())):
                return False
            source._pending_miracles.append(card)
            return True

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            card = source._pending_miracles.pop() if source._pending_miracles else None
            if ctrl is None or card is None:
                return
            # The card must still be in hand when the window resolves.
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost, spell=card):
                return
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                return
            ctrl.mana_pool.pay(miracle_cost, spell=card)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Opponent-upkeep loot
    # ------------------------------------------------------------------

    def _register_upkeep_loot(self, game: GameState) -> None:
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.game import discard, draw_card
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(
                hand_cards, "Discard a card to draw a card? (None to decline)"
            )
            if chosen is None or chosen not in hand_cards:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
