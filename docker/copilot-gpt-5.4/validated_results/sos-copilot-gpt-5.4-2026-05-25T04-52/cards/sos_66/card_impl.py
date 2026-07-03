"""Card implementation for Run Behind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RunBehind(Instant):
    """Run Behind."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Run Behind")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast if it targets an attacking creature.\n"
            "Target creature's owner puts it on their choice of the top or bottom of their library.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game: GameState) -> int:  # noqa: ARG002
        targets = getattr(self, "_casting_targets", getattr(self, "chosen_targets", []))
        target = targets[0] if targets else None
        return 1 if getattr(target, "is_attacking", False) else 0

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if target is None:
            return
        if not any(game.get_battlefield(player).contains(target) for player in game.players):
            return
        owner = getattr(target, "owner", None)
        if owner is None:
            return

        put_on_top = owner.choose_yes_no(
            f"Put {getattr(target, 'name', 'target creature')} on top of your library?"
        )
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.LIBRARY)
        if not put_on_top:
            library = game.get_library(owner)
            if library.contains(target):
                library.remove(target)
                library.add(target, position="bottom")
