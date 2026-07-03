"""Card implementation for Practiced Offense."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PracticedOffense(Sorcery):
    """Practiced Offense."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Practiced Offense")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on each creature target player controls. Target creature gains "
            "your choice of double strike or lifelink until end of turn.\nFlashback {1}{W}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{1}{W}")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if len(targets) > 0 else None
        target_creature = targets[1] if len(targets) > 1 else None

        if target_player is not None:
            for creature in game.get_battlefield(target_player).get_all():
                if not isinstance(creature, Creature):
                    continue
                creature.plus_one_counters += 1
                creature._base_plus_one_counters = creature.plus_one_counters

        if not isinstance(target_creature, Creature):
            return
        creature_controller = getattr(target_creature, "controller", None)
        if creature_controller is None or not game.get_battlefield(creature_controller).contains(target_creature):
            return
        if self.controller is None:
            return

        choice = self.controller.choose(
            [Keyword.DOUBLE_STRIKE, Keyword.LIFELINK],
            "Choose double strike or lifelink for Practiced Offense",
        )
        granted_keyword = choice if choice in (Keyword.DOUBLE_STRIKE, Keyword.LIFELINK) else Keyword.DOUBLE_STRIKE

        def _apply(game: GameState) -> None:  # noqa: ARG001
            target_creature.keywords |= granted_keyword

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
