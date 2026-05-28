"""Card implementation for Lorehold, the Historian.

{3}{R}{W} 5/5 Legendary Creature — Elder Dragon
Flying, haste
Each instant and sorcery card in your hand has miracle {2}.
At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — Legendary Elder Dragon.

    Flying, haste.
    Static: Each instant and sorcery card in controller's hand has miracle {2}.
    Triggered: At the beginning of each opponent's upkeep, may discard to draw.
    """

    def __init__(
        self,
        name: str = "Lorehold, the Historian",
        owner: Any = None,
        base_power: int = 5,
        base_toughness: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            mana_cost=ManaCost(generic=3, pips={ManaType.RED: 1, ManaType.WHITE: 1}),
            card_types={CardType.CREATURE},
            subtypes={"Elder", "Dragon"},
            supertypes={Supertype.LEGENDARY},
            keywords=Keyword.FLYING | Keyword.HASTE,
            rules_text=(
                "Flying, haste\n"
                "Each instant and sorcery card in your hand has miracle {2}. "
                "(You may cast a card for its miracle cost when you draw it if "
                "it's the first card you drew this turn.)\n"
                "At the beginning of each opponent's upkeep, you may discard a "
                "card. If you do, draw a card."
            ),
            owner=owner,
            base_power=base_power,
            base_toughness=base_toughness,
            **kwargs,
        )
        self._miracle_effect: ContinuousEffect | None = None

    # ------------------------------------------------------------------
    # Triggers and continuous effects
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the opponent-upkeep trigger and miracle continuous effect."""
        controller = self.controller

        # --- Static continuous effect: grant miracle {2} to instants/sorceries in hand ---
        def _apply_miracle_grant(game: GameState) -> None:
            """Grant miracle_cost to each instant/sorcery in controller's hand."""
            if controller is None:
                return
            # Self-checking: if Lorehold is no longer on the battlefield, remove effect
            bf = controller.zones[Zone.BATTLEFIELD]
            if not bf.contains(self):
                # Clean up: remove miracle_cost from hand cards
                hand = controller.zones[Zone.HAND]
                for card in hand.get_all():
                    if hasattr(card, "miracle_cost"):
                        card.miracle_cost = None
                if self._miracle_effect is not None:
                    game.effect_manager.remove(self._miracle_effect)
                    self._miracle_effect = None
                return
            hand = controller.zones[Zone.HAND]
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    card.miracle_cost = ManaCost(generic=2)

        self._miracle_effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            apply=_apply_miracle_grant,
            duration=DURATION_PERMANENT,
        )
        game.effect_manager.add(self._miracle_effect)

        # --- Miracle trigger: on first draw each turn, offer miracle cast ---
        # Mutable container to capture the drawn card from the condition check
        _miracle_drawn_card: list[Any] = []

        def _miracle_condition(game: GameState, event: DrawsCardTriggeredEvent) -> bool:
            """Only fire if the drawn card's controller is Lorehold's controller
            and it's the first card drawn this turn, and the card is instant/sorcery."""
            if event.player is not controller:
                return False
            # Check if this is the first card drawn this turn
            cards_drawn = getattr(event.player, "cards_drawn_this_turn", 0)
            if cards_drawn != 1:
                return False
            # Check if the drawn card is an instant or sorcery
            card = event.card
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Capture the specific drawn card for the effect
            _miracle_drawn_card.clear()
            _miracle_drawn_card.append(card)
            return True

        def _miracle_effect_fn(game: GameState) -> None:
            """Offer to cast the drawn card for its miracle cost."""
            if controller is None:
                return
            if not _miracle_drawn_card:
                return
            miracle_card = _miracle_drawn_card[0]
            # Apply continuous effects to ensure miracle_cost is set on hand cards
            game.effect_manager.apply_all(game)
            # Verify the card is still in hand and has miracle_cost
            hand = controller.zones[Zone.HAND]
            if not hand.contains(miracle_card):
                return
            if not (hasattr(miracle_card, "miracle_cost") and miracle_card.miracle_cost is not None):
                return
            card_types = getattr(miracle_card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return
            # Ask the player if they want to cast it for the miracle cost
            if controller.choose_yes_no(
                f"Cast {getattr(miracle_card, 'name', 'card')} for its miracle cost?"
            ):
                from engine.casting import cast_spell_for_cost
                cast_spell_for_cost(game, controller, miracle_card, miracle_card.miracle_cost)

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect_fn,
            source=self,
            controller=controller,
        ))

        # --- Opponent upkeep trigger: may discard, if you do draw ---
        def _upkeep_condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            """Fire only on opponents' upkeeps, not controller's own."""
            # The active player during upkeep is the turn player
            return game.active_player is not controller

        def _upkeep_effect(game: GameState) -> None:
            """May discard a card. If you do, draw a card."""
            if controller is None:
                return
            hand = controller.zones[Zone.HAND]
            hand_cards = hand.get_all()
            if not hand_cards:
                return
            # Ask if the player wants to discard
            if not controller.choose_yes_no("Discard a card to draw a card?"):
                return
            # Choose which card to discard
            card_to_discard = controller.choose_card(
                hand_cards, "Choose a card to discard"
            )
            if card_to_discard is None:
                return
            # Discard
            from engine.game import discard, draw_card
            discard(game, controller, card_to_discard)
            # Draw
            draw_card(game, controller)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_upkeep_condition,
            effect=_upkeep_effect,
            source=self,
            controller=controller,
        ))

    def register_replacement_effects(self, game: GameState) -> None:
        """No replacement effects for Lorehold."""

    def _on_leave_battlefield(self, game: GameState) -> None:
        """Clean up continuous effect and triggers when leaving battlefield."""
        # Remove the miracle continuous effect
        if self._miracle_effect is not None:
            game.effect_manager.remove(self._miracle_effect)
            self._miracle_effect = None
        # Unregister all triggers from this source
        game.trigger_manager.unregister(self)
        # Remove miracle_cost from cards in hand (effect manager will handle
        # this on next apply_all, but let's be explicit)
        if self.controller is not None:
            hand = self.controller.zones[Zone.HAND]
            for card in hand.get_all():
                if hasattr(card, "miracle_cost"):
                    del card.miracle_cost

