"""Card implementation for Homesickness."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import add_counter, draw_card, tap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Homesickness(Instant):
    """Homesickness."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Homesickness")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "zones") and hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = list(getattr(self, "chosen_targets", []))
        player = targets[0] if targets else None
        if player is not None and hasattr(player, "zones"):
            draw_card(game, player)
            draw_card(game, player)

        seen_targets: set[int] = set()
        for target in targets[1:3]:
            if not isinstance(target, Creature):
                continue
            if id(target) in seen_targets:
                continue
            if not any(game.get_battlefield(player_obj).contains(target) for player_obj in game.players):
                continue
            seen_targets.add(id(target))
            tap(game, target)
            add_counter(game, target, "stun")
