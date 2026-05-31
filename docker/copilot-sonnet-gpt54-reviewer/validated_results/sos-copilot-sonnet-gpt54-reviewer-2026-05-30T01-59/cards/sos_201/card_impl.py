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
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Stores the card drawn as a miracle candidate until the trigger resolves.
        self._miracle_candidate: Any = None

    # ------------------------------------------------------------------
    # Triggered abilities
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle and opponent-upkeep triggers."""
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        lorehold = self

        # ---- Miracle: grants instant/sorceries in hand miracle {2} ----

        def _miracle_condition(game: "GameState", event: DrawsCardTriggeredEvent) -> bool:
            # Only trigger for Lorehold's controller drawing their first card.
            if event.player is not lorehold.controller:
                return False
            if getattr(event.player, "cards_drawn_this_turn", 0) != 1:
                return False
            ct = getattr(event.card, "card_types", set())
            if CardType.INSTANT not in ct and CardType.SORCERY not in ct:
                return False
            # Capture the card for the effect closure.
            lorehold._miracle_candidate = event.card
            return True

        def _miracle_effect(game: "GameState") -> None:
            card = lorehold._miracle_candidate
            lorehold._miracle_candidate = None
            if card is None:
                return
            controller = lorehold.controller
            # Lorehold must still be on the battlefield.
            if not game.get_battlefield(controller).contains(lorehold):
                return
            # Card must still be in hand.
            if not game.get_hand(controller).contains(card):
                return
            # Offer miracle cast for {2}.
            if controller.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                # Remove from hand and resolve (simplified miracle cast).
                game.get_hand(controller).remove(card)
                card.controller = controller
                card.owner = getattr(card, "owner", controller)
                card.on_resolve(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=self.controller,
            )
        )

        # ---- Opponent upkeep: may discard, if you do draw ----

        def _upkeep_condition(
            game: "GameState", event: BeginningOfUpkeepTriggeredEvent
        ) -> bool:
            # Fires at the beginning of each opponent's upkeep.
            return game.active_player is not lorehold.controller

        def _upkeep_effect(game: "GameState") -> None:
            controller = lorehold.controller
            # Lorehold must still be on the battlefield.
            if not game.get_battlefield(controller).contains(lorehold):
                return
            # May discard.
            if not controller.choose_yes_no("Discard a card?"):
                return
            hand = game.get_hand(controller)
            hand_cards = hand.get_all()
            if not hand_cards:
                return
            from engine.game import discard, draw_card
            from engine.player import ScriptExhaustedError

            try:
                card_to_discard = controller.choose_card(
                    hand_cards, "choose a card to discard"
                )
            except (ScriptExhaustedError, NotImplementedError):
                card_to_discard = hand_cards[-1]

            discard(game, controller, card_to_discard)
            draw_card(game, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=self.controller,
            )
        )
