"""Card implementation for Burrog Barrage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class BurrogBarrage(Instant):
    """Burrog Barrage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Barrage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
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
        source_creature = chosen_targets[0] if chosen_targets else None
        target_creature = chosen_targets[1] if len(chosen_targets) > 1 else None
        controller = self.controller
        if not isinstance(source_creature, Creature) or controller is None:
            return
        if not source_creature.is_on_battlefield(game) or source_creature.controller is not controller:
            return

        cast_history = getattr(game, "spells_cast_this_turn", [])
        current_cast_serial = getattr(self, "_cast_turn_serial", None)

        def _is_other_instant_or_sorcery_cast(entry: Any) -> bool:
            caster = getattr(entry, "player", None)
            spell = getattr(entry, "card", None)
            cast_serial = getattr(entry, "cast_serial", None)
            if caster is None and isinstance(entry, tuple):
                caster = entry[0] if len(entry) > 0 else None
                spell = entry[1] if len(entry) > 1 else None
                cast_serial = entry[2] if len(entry) > 2 else None
            if caster is not controller:
                return False
            if not bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}):
                return False
            if current_cast_serial is not None and cast_serial is not None:
                return cast_serial != current_cast_serial
            return spell is not self

        cast_another_spell = any(
            _is_other_instant_or_sorcery_cast(entry) for entry in cast_history
        )
        if cast_another_spell:
            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=lambda _game, creature=source_creature: setattr(
                        creature,
                        "modified_power",
                        creature.modified_power + 1,
                    ),
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        if not isinstance(target_creature, Creature):
            return
        opposing_controller = getattr(target_creature, "controller", None)
        if opposing_controller is None or opposing_controller is controller:
            return
        if not target_creature.is_on_battlefield(game):
            return
        deal_damage(game, source_creature, target_creature, source_creature.power)
