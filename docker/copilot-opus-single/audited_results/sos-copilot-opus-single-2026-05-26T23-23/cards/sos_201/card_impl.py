"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _UpkeepTrigger:
    """Trigger descriptor for opponent's upkeep discard-to-draw."""

    def __init__(self, source: "LoreholdTheHistorian") -> None:
        self.source = source
        self.description = "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card."


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

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
            "Flying, haste\nEach instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle granting and upkeep trigger."""
        self._game = game
        self._apply_miracle_to_hand(game)

        # Hook into the hand zone's add method to apply miracle on new cards
        controller = self.controller
        if controller is not None:
            hand_zone = game.get_hand(controller)
            original_add = hand_zone.add
            source = self

            def _hooked_add(obj: Any, position: str = "top") -> None:
                original_add(obj, position)
                # Apply miracle to the newly added card if applicable
                if CardType.INSTANT in getattr(obj, "card_types", set()) or \
                   CardType.SORCERY in getattr(obj, "card_types", set()):
                    obj.miracle_cost = ManaCost.parse("{2}")

            hand_zone.add = _hooked_add  # type: ignore[method-assign]

        # Register phase listener for ongoing miracle application
        def _on_phase_change(g: Any, phase: Any, step: Any) -> None:
            self._apply_miracle_to_hand(g)

        game.phase_listeners.append(_on_phase_change)

    def _apply_miracle_to_hand(self, game: "GameState") -> None:
        """Grant miracle {2} to all instants/sorceries in controller's hand."""
        controller = self.controller
        if controller is None:
            return
        hand = game.get_hand(controller)
        miracle_cost = ManaCost.parse("{2}")
        for card in hand.get_all():
            if CardType.INSTANT in getattr(card, "card_types", set()) or \
               CardType.SORCERY in getattr(card, "card_types", set()):
                card.miracle_cost = miracle_cost
            else:
                if hasattr(card, "miracle_cost"):
                    del card.miracle_cost

    def can_miracle(self, game: "GameState", card: Any) -> bool:
        """Check if a card can be cast for its miracle cost.

        Miracle is only available if the card is the first drawn this turn.
        """
        controller = self.controller
        if controller is None:
            return False
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return False
        cards_drawn = getattr(game, "cards_drawn_this_turn", {})
        drawn_count = cards_drawn.get(controller, 0)
        return drawn_count <= 1

    def get_triggers(self, game: "GameState") -> list[Any]:
        """Return triggers that should fire given current game state."""
        controller = self.controller
        if controller is None:
            return []

        from engine.types import Phase, Step
        if game.phase == Phase.BEGINNING and game.step == Step.UPKEEP:
            active_player = game.players[game.active_player_index]
            if active_player is not controller:
                return [_UpkeepTrigger(self)]
        return []

    def on_upkeep_trigger(self, game: "GameState", discard: bool = True) -> None:
        """Resolve the upkeep trigger. May discard a card to draw a card."""
        from engine.game import draw_card, discard as engine_discard

        controller = self.controller
        if controller is None:
            return

        if not discard:
            return

        hand = game.get_hand(controller)
        hand_cards = hand.get_all()
        if not hand_cards:
            return

        card_to_discard = hand_cards[0]
        engine_discard(game, controller, card_to_discard)
        draw_card(game, controller)

    def upkeep_trigger_effect(self, game: "GameState") -> None:
        """Alternative trigger resolution method (always discards)."""
        self.on_upkeep_trigger(game, discard=True)
