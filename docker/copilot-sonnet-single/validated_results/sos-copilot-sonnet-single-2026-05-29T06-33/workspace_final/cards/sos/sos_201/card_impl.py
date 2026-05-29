"""Card implementation for Lorehold, the Historian.

# UNVERIFIED: miracle cast pipeline not fully tested — alternate-cost casting
# integration needed
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

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
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the draw trigger and opponent's upkeep trigger."""
        source = self
        controller = self.controller

        # -----------------------------------------------------------------------
        # Continuous effect: grant miracle {2} to instants/sorceries in hand
        # -----------------------------------------------------------------------
        miracle_cost = ManaCost.parse("{2}")

        def _apply_miracle_grant(g: "GameState") -> None:
            """Grant miracle_cost to each instant/sorcery in controller's hand."""
            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            # First, clear miracle_cost from all hand instants/sorceries so that
            # when Lorehold is not on the battlefield the cost is removed.
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    if hasattr(card, "miracle_cost"):
                        del card.miracle_cost
            # Check that Lorehold is actually on the battlefield before re-granting
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return
            for card in hand.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    card.miracle_cost = miracle_cost

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_miracle_grant,
            duration=DURATION_PERMANENT,
        ))

        # -----------------------------------------------------------------------
        # Trigger: when controller draws a card, mark first-draw instants/sorceries
        # -----------------------------------------------------------------------
        def _draw_condition_immediate(g: Any, event: Any) -> bool:
            """Immediately mark first-drawn instant/sorcery as miracle-eligible.

            The marking is applied inline (as a condition side-effect) so it
            takes effect before draw_card returns — no stack resolution needed.
            Returns False so no redundant stack object is pushed.
            """
            ctrl = source.controller
            if ctrl is None:
                return False
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return False
            if event.player is not ctrl:
                return False
            # cards_drawn_this_turn was already incremented by draw_card
            drawn_count = getattr(ctrl, "cards_drawn_this_turn", 1)
            if drawn_count == 1:
                card = event.card
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    card.can_cast_as_miracle = True
            # Return False: effect was applied inline; no stack push needed.
            return False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition_immediate,
                effect=lambda g: None,  # no-op; marking done in condition
                source=source,
                controller=controller,
            )
        )

        # -----------------------------------------------------------------------
        # Trigger: at the beginning of each opponent's upkeep, may discard→draw
        # -----------------------------------------------------------------------
        def _upkeep_condition(g: Any, event: Any) -> bool:
            """Fire only on an opponent's upkeep while Lorehold is on the battlefield."""
            ctrl = source.controller
            if ctrl is None:
                return False
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return False
            active = g.active_player
            return active is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            """Controller may discard a card; if they do, draw a card."""
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            wants_to_discard = ctrl.choose_yes_no(
                "Lorehold, the Historian: Discard a card to draw a card?"
            )
            if not wants_to_discard:
                return
            hand = ctrl.zones[Zone.HAND]
            hand_cards = list(hand.get_all())
            if not hand_cards:
                return
            card_to_discard = ctrl.choose(
                hand_cards, "Choose a card to discard"
            )
            discard(g, ctrl, card_to_discard)
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
