"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class _MiracleHandZoneProxy:
    """Wraps a ZoneContainer for the controller's hand to auto-apply miracle_cost
    to instants/sorceries when they are added, and auto-remove it on removal.

    This proxy delegates all attribute access to the underlying ZoneContainer
    but intercepts ``add`` and ``remove`` to manage the ``miracle_cost`` attribute
    on cards that are instants or sorceries belonging to the Lorehold controller.
    """

    def __init__(self, real_zone: Any, controller: Any, miracle_cost: ManaCost) -> None:
        object.__setattr__(self, "_real_zone", real_zone)
        object.__setattr__(self, "_controller", controller)
        object.__setattr__(self, "_miracle_cost", miracle_cost)

    def add(self, obj: Any, position: str = "top") -> None:
        """Add card to zone, applying miracle_cost if it's an instant/sorcery."""
        self._real_zone.add(obj, position)
        if _is_instant_or_sorcery(obj):
            obj.miracle_cost = self._miracle_cost

    def remove(self, obj: Any) -> None:
        """Remove card from zone, cleaning up miracle_cost."""
        self._real_zone.remove(obj)
        if hasattr(obj, "miracle_cost") and _is_instant_or_sorcery(obj):
            del obj.miracle_cost

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_zone, name)

    def __len__(self) -> int:
        return len(self._real_zone)

    def __repr__(self) -> str:
        return repr(self._real_zone)


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian -- {3}{R}{W} -- Legendary Creature -- Elder Dragon -- 5/5.

    Flying, haste
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
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Miracle granting + Upkeep trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register miracle granting and the opponent's upkeep loot trigger."""
        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        miracle_cost = ManaCost.parse("{2}")

        # --- Miracle granting: wrap the controller's hand zone ---
        # Install a proxy on the hand zone that auto-applies miracle_cost
        # to instants/sorceries when they enter the hand.
        from engine.types import Zone

        hand_zone = controller.zones[Zone.HAND]

        # Only wrap if not already wrapped (avoid double-wrapping).
        if not isinstance(hand_zone, _MiracleHandZoneProxy):
            proxy = _MiracleHandZoneProxy(hand_zone, controller, miracle_cost)
            controller.zones._zones[Zone.HAND] = proxy

            # Also apply miracle_cost to any instants/sorceries already in hand.
            for card in hand_zone.get_all():
                if _is_instant_or_sorcery(card):
                    card.miracle_cost = miracle_cost

        # --- Opponent's upkeep trigger ---
        source = self

        def _upkeep_condition(game: GameState, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            """Fire only on an opponent's upkeep (active player is not the controller)."""
            return game.active_player is not controller

        def _upkeep_effect(game: GameState) -> None:
            """May discard a card. If you do, draw a card."""
            from engine.game import discard, draw_card

            # Check if the controller has cards in hand
            player_hand = game.get_hand(controller)
            if len(player_hand) == 0:
                # Cannot discard, so nothing happens
                # Still consume the "may" choice if scripted
                try:
                    chose_to_discard = controller.choose_yes_no(
                        "Discard a card to draw a card?"
                    )
                except Exception:
                    return
                return

            # Ask the controller if they want to discard
            chose_to_discard = controller.choose_yes_no(
                "Discard a card to draw a card?"
            )
            if not chose_to_discard:
                return

            # Choose a card to discard
            hand_cards = player_hand.get_all()
            if not hand_cards:
                return

            # Use choose_card for selecting which card to discard
            # If there is only one card, discard it automatically
            if len(hand_cards) == 1:
                card_to_discard = hand_cards[0]
            else:
                card_to_discard = controller.choose_card(
                    hand_cards, "Choose a card to discard"
                )

            discard(game, controller, card_to_discard)
            draw_card(game, controller)

        trigger = TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_upkeep_condition,
            effect=_upkeep_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
