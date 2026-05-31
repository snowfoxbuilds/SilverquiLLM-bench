"""Card implementation for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Creature — Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    (You may cast a card for its miracle cost when you draw it if it's the
    first card you drew this turn.)
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
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the miracle-grant draw trigger and opponent's-upkeep loot trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller or game.active_player

        # ------------------------------------------------------------------
        # Miracle grant: when the controller draws their first card of the
        # turn, if that card is an instant or sorcery, mark it as miracle-
        # eligible with miracle cost {2}.
        # ------------------------------------------------------------------
        _miracle_state: list[Any] = [None]  # captures the drawn card across condition→effect

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Only first card drawn this turn
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            _miracle_state[0] = card
            return True

        def _miracle_effect(g: "GameState") -> None:
            card = _miracle_state[0]
            if card is None:
                return
            card.miracle_eligible = True
            card.miracle_cost = ManaCost.parse("{2}")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=source,
                controller=controller,
            )
        )

        # ------------------------------------------------------------------
        # Opponent's upkeep: may discard a card; if you do, draw a card.
        # ------------------------------------------------------------------
        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return g.active_player is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = g.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            try:
                chosen = ctrl.choose(
                    cards_in_hand,
                    "Discard a card for Lorehold's upkeep trigger?",
                )
            except Exception:
                return  # Player chose not to discard (no script or declined)
            if chosen is None:
                return
            from engine.game import discard, draw_card
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=source,
                controller=controller,
            )
        )
