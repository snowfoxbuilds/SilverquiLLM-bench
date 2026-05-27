"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
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
            (
                "Flying, haste\n"
                "Each instant and sorcery card in your hand has miracle {2}. "
                "(You may cast a card for its miracle cost when you draw it if "
                "it's the first card you drew this turn.)\n"
                "At the beginning of each opponent's upkeep, you may discard a "
                "card. If you do, draw a card."
            ),
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB effect: grant miracle {2} to all instants/sorceries already in controller's hand."""
        super().on_resolve(game)
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        _miracle_cost = ManaCost.parse("{2}")
        hand = controller.zones[Zone.HAND]
        for card in hand.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                card.miracle_cost = _miracle_cost

    def register_triggers(self, game: "GameState") -> None:
        """Register the upkeep trigger and the miracle draw trigger."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # ------------------------------------------------------------------
        # 1) Opponent's upkeep trigger: may discard → draw
        # ------------------------------------------------------------------

        def _upkeep_condition(game: Any, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            """Fire only on opponents' upkeeps (not the controller's own upkeep)."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
            """May discard a card. If you do, draw a card."""
            from engine.game import discard as _discard, draw_card as _draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            hand_cards = hand.get_all()
            if not hand_cards:
                # No cards to discard — do nothing
                return
            wants_to_discard = ctrl.choose_yes_no(
                "Lorehold, the Historian: May discard a card to draw a card?"
            )
            if wants_to_discard:
                # Let the player choose which card to discard.
                from engine.player import ScriptExhaustedError
                try:
                    card_to_discard = ctrl.choose_card(
                        hand_cards,
                        "Lorehold, the Historian: choose a card to discard",
                    )
                    if card_to_discard is None or not hand.contains(card_to_discard):
                        card_to_discard = hand_cards[-1]
                except (ScriptExhaustedError, NotImplementedError):
                    card_to_discard = hand_cards[-1]
                _discard(game, ctrl, card_to_discard)
                _draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )

        # ------------------------------------------------------------------
        # 2) Miracle mechanic: drawn instant/sorcery (first draw) gets miracle {2}
        #    The miracle cost is granted immediately in the condition as a side
        #    effect, since the trigger fires in response to the draw event and
        #    the cost must be available right away for the player to use it.
        # ------------------------------------------------------------------

        _miracle_cost = ManaCost.parse("{2}")

        def _draw_condition(game: Any, event: DrawsCardTriggeredEvent) -> bool:
            """Grant miracle {2} to any instant/sorcery drawn as the first card this turn."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Only grant to the controller's draws
            if event.player is not ctrl:
                return False
            # Only the first card drawn this turn
            drawn_count = getattr(event.player, "cards_drawn_this_turn", 0)
            if drawn_count != 1:
                return False
            card = event.card
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Grant miracle cost immediately (observable side effect)
            card.miracle_cost = _miracle_cost
            return True

        def _draw_effect(game: "GameState") -> None:
            """No additional effect needed — miracle cost was granted in condition."""

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_draw_effect,
                source=self,
                controller=controller,
            )
        )

