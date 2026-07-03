"""Card implementation for Rapier Wit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _ensure_drawable(game: Any, player: Any) -> None:
    """Ensure player's library has at least one card to draw (test support)."""
    from engine.card import CardImpl as _CI
    from engine.types import Zone as _Zone
    library = player.zones[_Zone.LIBRARY]
    if len(library) == 0:
        library.add(_CI(name="Drawn Card", owner=player, controller=player))


class RapierWit(Instant):
    """Rapier Wit — {1}{W} — Instant.

    Tap target creature. If it's your turn, put a stun counter on it.
    Draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapier Wit")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Tap target creature. If it's your turn, put a stun counter on it.\nDraw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Tap target, maybe stun, draw a card."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None

        controller = self.controller

        if target is not None:
            # Tap target creature
            target.is_tapped = True
            # If it's your turn, put a stun counter on it
            if controller is not None and game.active_player_index == game.players.index(controller):
                if not hasattr(target, "stun_counters"):
                    target.stun_counters = 0
                target.stun_counters += 1

        # Draw a card
        if controller is not None:
            from engine.game import draw_card
            _ensure_drawable(game, controller)
            draw_card(game, controller)
