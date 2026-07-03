"""Card implementation for Chelonian Tackle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ChelonianTackle(Sorcery):
    """Chelonian Tackle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chelonian Tackle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        your_creature = TargetRequirement(
            filter_fn=lambda obj, _controller=controller: (
                isinstance(obj, Creature) and getattr(obj, "controller", None) is _controller
            ),
            description="target creature you control",
            zone=Zone.BATTLEFIELD,
        )
        opposing_creature = TargetRequirement(
            filter_fn=lambda obj, _controller=controller: (
                isinstance(obj, Creature)
                and _controller is not None
                and getattr(obj, "controller", None) is not _controller
            ),
            description="up to one target creature an opponent controls",
            zone=Zone.BATTLEFIELD,
        )
        opposing_creature.min_targets = 0  # type: ignore[attr-defined]
        return [your_creature, opposing_creature]

    def on_resolve(self, game: GameState) -> None:
        chosen_targets = getattr(self, "chosen_targets", [])
        your_creature = chosen_targets[0] if chosen_targets else None
        opposing_creature = chosen_targets[1] if len(chosen_targets) > 1 else None
        controller = self.controller
        if not isinstance(your_creature, Creature) or controller is None:
            return
        if not your_creature.is_on_battlefield(game) or your_creature.controller is not controller:
            return

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=lambda _game, creature=your_creature: setattr(
                    creature,
                    "modified_toughness",
                    creature.modified_toughness + 10,
                ),
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)

        if not isinstance(opposing_creature, Creature):
            return
        opposing_controller = getattr(opposing_creature, "controller", None)
        if opposing_controller is None or opposing_controller is controller:
            return
        if not opposing_creature.is_on_battlefield(game):
            return

        deal_damage(game, your_creature, opposing_creature, your_creature.power)
        deal_damage(game, opposing_creature, your_creature, opposing_creature.power)
