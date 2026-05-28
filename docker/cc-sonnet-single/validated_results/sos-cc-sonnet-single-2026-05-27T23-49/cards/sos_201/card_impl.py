"""Card implementation for Lorehold, the Historian (SOS 201).

Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5

Flying, haste
Each instant and sorcery card in your hand has miracle {2}.
(You may cast a card for its miracle cost when you draw it if it's the
first card you drew this turn.)
At the beginning of each opponent's upkeep, you may discard a card.
If you do, draw a card.

SOS collector number 201.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, LeavesBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_MIRACLE_COST = ManaCost.parse("{2}")


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


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
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword(0))
        kwargs["keywords"] = kwargs["keywords"] | Keyword.FLYING | Keyword.HASTE
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Storage for the original ZoneContainer.add so we can restore it.
        self._original_hand_add: Any = None
        self._hooked_hand_zone: Any = None  # reference to the patched zone

    # ------------------------------------------------------------------
    # Miracle granting — hook the controller's hand zone
    # ------------------------------------------------------------------

    def _apply_miracle_hook(self, game: "GameState") -> None:
        """Install a hook on the controller's HAND zone that tags instants and
        sorceries with miracle_cost = {2} when they enter the zone.

        Also immediately tags all existing instants/sorceries in the hand.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        hand = controller.zones[Zone.HAND]

        # Tag cards already in hand.
        for card in hand.get_all():
            if _is_instant_or_sorcery(card):
                card.miracle_cost = _MIRACLE_COST

        # Patch the add method to tag future additions.
        # Guard against double-patching.
        if self._hooked_hand_zone is hand:
            return

        source = self  # capture for closure

        original_add = hand.add

        def _patched_add(obj: Any, position: str = "top") -> None:
            original_add(obj, position)
            # Only grant miracle while Lorehold is still on the battlefield.
            # source._hooked_hand_zone is set to None by _remove_miracle_hook()
            # when Lorehold leaves, so this acts as a battlefield-presence guard.
            if source._hooked_hand_zone is not None and _is_instant_or_sorcery(obj):
                obj.miracle_cost = _MIRACLE_COST

        hand.add = _patched_add  # type: ignore[method-assign]
        self._original_hand_add = original_add
        self._hooked_hand_zone = hand

    def _remove_miracle_hook(self) -> None:
        """Restore the original add method on the hand zone (cleanup)."""
        if self._hooked_hand_zone is not None and self._original_hand_add is not None:
            self._hooked_hand_zone.add = self._original_hand_add  # type: ignore[method-assign]
        self._hooked_hand_zone = None
        self._original_hand_add = None

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the opponent-upkeep loot trigger and miracle-grant hook."""
        from engine.game import draw_card, discard as engine_discard

        source = self
        controller = getattr(self, "controller", None)
        if controller is None:
            controller = game.active_player

        # --- Miracle granting ---
        self._apply_miracle_hook(game)

        # --- Upkeep loot trigger ---
        def _condition(g: "GameState", event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Fires on opponent's upkeep — active player is NOT the controller.
            return g.active_player is not ctrl

        def _effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Ask controller if they want to discard
            try:
                wants_discard = ctrl.choose_yes_no(
                    "Discard a card? (Lorehold, the Historian)"
                )
            except Exception:
                wants_discard = True

            if not wants_discard:
                return

            # Choose a card to discard from hand
            hand = g.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                # No cards to discard — ability fizzles gracefully.
                return

            try:
                chosen = ctrl.choose_card(
                    cards_in_hand, "Choose a card to discard (Lorehold)"
                )
            except Exception:
                chosen = cards_in_hand[0] if cards_in_hand else None

            if chosen is None or not hand.contains(chosen):
                return

            engine_discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Leaves-battlefield cleanup: remove miracle hook when Lorehold leaves ---
        def _leaves_condition(g: "GameState", event: Any) -> bool:
            return event.permanent is source

        def _leaves_effect(g: "GameState") -> None:
            source._remove_miracle_hook()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leaves_condition,
                effect=_leaves_effect,
                source=self,
                controller=controller,
            )
        )
