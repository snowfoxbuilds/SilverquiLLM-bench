"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault(
            "supertypes",
            {Supertype.LEGENDARY},
        )
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_miracle_cost(self, card: Any) -> ManaCost | None:
        """Return the miracle cost {2} for instants and sorceries owned by controller.

        Returns ManaCost({2}) if card is an instant or sorcery controlled by
        the same player as this permanent.  Returns None otherwise.
        """
        # Only grant miracle to cards controlled/owned by our controller.
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return None
        card_ctrl = getattr(card, "controller", None) or getattr(card, "owner", None)
        if card_ctrl is not None and ctrl is not card_ctrl:
            return None

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return ManaCost.parse("{2}")
        return None

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent-upkeep trigger."""
        from engine.triggers import TriggerRegistration
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.game import draw_card, discard
        from engine.player import ScriptExhaustedError

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: Any) -> bool:
            """Fire only during an opponent's upkeep (not our controller's)."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Active player is the player whose upkeep it is.
            # We want to fire when it is NOT our controller's upkeep.
            return game.active_player is not ctrl

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # May discard a card
            try:
                wants_to_discard = ctrl.choose_yes_no(
                    "Lorehold, the Historian: Discard a card to draw a card?"
                )
            except (ScriptExhaustedError, Exception):
                wants_to_discard = True  # default to yes if no answer scripted

            if not wants_to_discard:
                return

            # Discard a card from hand
            hand = game.get_hand(ctrl)
            hand_cards = hand.get_all()
            if not hand_cards:
                return  # nothing to discard

            try:
                chosen = ctrl.choose_card(hand_cards, "Choose a card to discard")
            except (ScriptExhaustedError, Exception):
                chosen = hand_cards[0] if hand_cards else None

            if chosen is None:
                return

            discard(game, ctrl, chosen)
            # Draw a card
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
