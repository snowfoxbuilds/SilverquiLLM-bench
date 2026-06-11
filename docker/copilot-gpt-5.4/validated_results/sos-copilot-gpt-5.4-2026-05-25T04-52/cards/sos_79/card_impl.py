"""Card implementation for Dissection Practice."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent, LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DissectionPractice(Instant):
    """Dissection Practice."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dissection Practice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target opponent loses 1 life and you gain 1 life.\nUp to one target creature "
            "gets +1/+1 until end of turn.\nUp to one target creature gets -1/-1 until end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        source = self
        return [
            TargetRequirement(
                filter_fn=lambda obj, _source=source: (
                    isinstance(obj, Player) and obj is not getattr(_source, "controller", None)
                ),
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target_opponent = chosen[0] if len(chosen) > 0 else None
        boosted = chosen[1] if len(chosen) > 1 else None
        shrunk = chosen[2] if len(chosen) > 2 else None
        controller = self.controller

        if controller is not None and isinstance(target_opponent, Player) and target_opponent is not controller:
            target_opponent.life -= 1
            controller.life += 1
            game.trigger_manager.fire_event(
                game,
                LosesLifeTriggeredEvent(player=target_opponent, amount=1),
            )
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=1),
            )

        if isinstance(boosted, Creature) and boosted.is_on_battlefield(game):
            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=lambda _game, target=boosted: _modify_stats(target, 1, 1),
                    duration=DURATION_END_OF_TURN,
                )
            )
        if isinstance(shrunk, Creature) and shrunk.is_on_battlefield(game):
            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=lambda _game, target=shrunk: _modify_stats(target, -1, -1),
                    duration=DURATION_END_OF_TURN,
                )
            )
        game.effect_manager.apply_all(game)


def _modify_stats(creature: Creature, power_delta: int, toughness_delta: int) -> None:
    creature.modified_power += power_delta
    creature.modified_toughness += toughness_delta
