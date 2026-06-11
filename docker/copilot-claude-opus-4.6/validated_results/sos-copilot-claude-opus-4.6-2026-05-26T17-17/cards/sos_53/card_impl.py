"""Card implementation for Homesickness."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Homesickness(Instant):
    """Homesickness — {4}{U}{U} Instant.

    Target player draws two cards. Tap up to two target creatures.
    Put a stun counter on each of them.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Homesickness")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="up to two target creatures",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import draw_card

        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return

        # First target is always the player
        player_target = targets[0]
        creature_targets = [t for t in targets[1:] if CardType.CREATURE in getattr(t, "card_types", set())]

        # Player draws two cards
        draw_card(game, player_target)
        draw_card(game, player_target)

        # Tap creatures and add stun counters
        for creature in creature_targets:
            creature.is_tapped = True
            if not hasattr(creature, "stun_counters"):
                creature.stun_counters = 0
            creature.stun_counters += 1
