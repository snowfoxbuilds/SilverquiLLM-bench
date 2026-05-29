"""Card implementation for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 Legendary Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    #: The miracle cost granted to instants/sorceries in hand.
    miracle_grant_cost: ManaCost = ManaCost.parse("{2}")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "keywords",
            Keyword.FLYING | Keyword.HASTE,
        )
        kwargs.setdefault(
            "rules_text",
            (
                "Flying, haste\n"
                "Each instant and sorcery card in your hand has miracle {2}.\n"
                "At the beginning of each opponent's upkeep, you may discard a card. "
                "If you do, draw a card."
            ),
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_enters_battlefield(self, game: GameState) -> None:
        """Called when Lorehold enters the battlefield.

        Immediately applies the miracle-grant continuous effect so that
        any instants/sorceries already in the controller's hand gain
        miracle {2}.
        """
        self.apply_miracle_grant(game)

    # ------------------------------------------------------------------
    # Miracle grant continuous effect
    # ------------------------------------------------------------------

    def apply_miracle_grant(self, game: GameState) -> None:
        """Grant miracle {2} to each instant/sorcery in controller's hand.

        This is a continuous effect: it sets ``miracle_cost`` on every
        eligible card currently in the controller's hand.  Cards that are
        not instants or sorceries (or belong to opponents) are left
        untouched.
        """
        controller = self.controller
        if controller is None:
            return

        hand = game.get_hand(controller)
        for card in hand.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                card.miracle_cost = self.miracle_grant_cost

    # ------------------------------------------------------------------
    # Triggered ability: opponent's upkeep — discard → draw
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the 'beginning of each opponent's upkeep' trigger."""
        source = self

        def _condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            """Fire only during an opponent's upkeep (not controller's own)."""
            active = game.active_player
            return active is not source.controller

        def _effect(game: GameState) -> None:
            """Optional discard → draw effect.

            The controller may choose to discard a card.  If they do, they
            then draw a card.  If they decline (or have no cards to discard),
            nothing happens.
            """
            controller = source.controller
            if controller is None:
                return

            # Check whether the controller wants to discard (optional)
            hand = game.get_hand(controller)
            hand_cards = list(hand.get_all())
            if not hand_cards:
                return

            # Player chooses whether to discard (you *may* discard)
            wants_discard = controller.choose_yes_no(
                "Lorehold, the Historian: Discard a card to draw a card?"
            )
            if not wants_discard:
                return

            # Player chooses which card to discard
            card_to_discard = controller.choose_card(
                hand_cards, "Choose a card to discard for Lorehold's ability"
            )
            from engine.game import discard as engine_discard, draw_card
            engine_discard(game, controller, card_to_discard)
            draw_card(game, controller)

        trigger = TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=self.controller,
        )
        game.trigger_manager.register(trigger)
