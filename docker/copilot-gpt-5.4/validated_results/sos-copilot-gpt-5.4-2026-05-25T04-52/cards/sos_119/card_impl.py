"""Card implementation for Impractical Joke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage, make_damage_unpreventable_this_turn
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ImpracticalJoke(Sorcery):
    """Impractical Joke."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Impractical Joke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        requirement = TargetRequirement(
            filter_fn=lambda obj: isinstance(obj, (Creature, Planeswalker)),
            description="up to one target creature or planeswalker",
            zone=Zone.BATTLEFIELD,
        )
        requirement.min_targets = 0  # type: ignore[attr-defined]
        requirement.max_targets = 1  # type: ignore[attr-defined]
        return [requirement]

    def on_resolve(self, game: GameState) -> None:
        make_damage_unpreventable_this_turn(game)
        target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
        if isinstance(target, Creature):
            target_controller = getattr(target, "controller", None)
            if target_controller is None or not game.get_battlefield(target_controller).contains(target):
                return
            deal_damage(game, self, target, 3)
        elif isinstance(target, Planeswalker):
            target_controller = getattr(target, "controller", None)
            if target_controller is None or not game.get_battlefield(target_controller).contains(target):
                return
            deal_damage(game, self, target, 3)
