"""Card implementation for Choreographed Sparks."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.casting import _normalize_chosen_targets
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.game import sacrifice
from benchmarks.sos.workspace.engine.stack import StackObject, copy_spell
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class ChoreographedSparks(Instant):
    """Choreographed Sparks."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Choreographed Sparks")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{R}"))
        super().__init__(**kwargs)

    def __copy__(self) -> Any:
        raise Exception(f"{self.name} can't be copied")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller

        def _is_your_instant_or_sorcery_spell(obj: object) -> bool:
            return (
                isinstance(obj, StackObject)
                and bool(getattr(obj, "is_spell", False))
                and getattr(obj, "controller", None) is controller
                and isinstance(getattr(obj, "source", None), (Instant, Sorcery))
            )

        def _is_your_creature_spell(obj: object) -> bool:
            return (
                isinstance(obj, StackObject)
                and bool(getattr(obj, "is_spell", False))
                and getattr(obj, "controller", None) is controller
                and isinstance(getattr(obj, "source", None), Creature)
            )

        instant_or_sorcery = TargetRequirement(
            filter_fn=_is_your_instant_or_sorcery_spell,
            description="target instant or sorcery spell you control",
            zone=Zone.STACK,
        )
        creature_spell = TargetRequirement(
            filter_fn=_is_your_creature_spell,
            description="target creature spell you control",
            zone=Zone.STACK,
        )
        instant_or_sorcery.min_targets = 0  # type: ignore[attr-defined]
        creature_spell.min_targets = 0  # type: ignore[attr-defined]
        return [instant_or_sorcery, creature_spell]

    def _choose_new_targets_for_copy(
        self,
        game: GameState,
        controller: Player,
        original: StackObject,
    ) -> list[object]:
        target_specs = getattr(original.source, "get_targets", lambda _game: [])(game)
        if not target_specs:
            return list(original.targets)

        original_target_groups = self._partition_original_targets(target_specs, list(original.targets))
        if original_target_groups is None:
            return list(original.targets)

        new_targets: list[object] = []
        for requirement, fallback_group in zip(target_specs, original_target_groups):
            try:
                chosen = controller.choose_target(target_specs, requirement)
            except Exception:
                chosen = None
            try:
                chosen_group = _normalize_chosen_targets(original.source, requirement, chosen)
            except Exception:
                chosen_group = list(fallback_group)
            filter_fn = getattr(requirement, "filter_fn", None)
            if len(chosen_group) != len(fallback_group):
                chosen_group = list(fallback_group)
            elif callable(filter_fn) and any(
                target is not None and not filter_fn(target) for target in chosen_group
            ):
                chosen_group = list(fallback_group)
            new_targets.extend(chosen_group)
        return new_targets if new_targets else list(original.targets)

    def _partition_original_targets(
        self,
        target_specs: list[TargetRequirement],
        original_targets: list[object],
    ) -> list[list[object]] | None:
        def _min_targets(requirement: TargetRequirement) -> int:
            return max(0, int(getattr(requirement, "min_targets", 1)))

        def _max_targets(requirement: TargetRequirement) -> int:
            return max(_min_targets(requirement), int(getattr(requirement, "max_targets", 1)))

        def _search(spec_index: int, target_index: int) -> list[list[object]] | None:
            if spec_index >= len(target_specs):
                return [] if target_index == len(original_targets) else None

            requirement = target_specs[spec_index]
            min_targets = _min_targets(requirement)
            max_targets = _max_targets(requirement)
            remaining_requirements = target_specs[spec_index + 1 :]
            remaining_targets = len(original_targets) - target_index
            remaining_min = sum(_min_targets(spec) for spec in remaining_requirements)
            remaining_max = sum(_max_targets(spec) for spec in remaining_requirements)
            lower_bound = max(min_targets, remaining_targets - remaining_max)
            upper_bound = min(max_targets, remaining_targets - remaining_min)
            filter_fn = getattr(requirement, "filter_fn", None)

            for count in range(upper_bound, lower_bound - 1, -1):
                candidate_group = original_targets[target_index : target_index + count]
                if callable(filter_fn) and any(
                    target is not None and not filter_fn(target) for target in candidate_group
                ):
                    continue
                remainder = _search(spec_index + 1, target_index + count)
                if remainder is not None:
                    return [candidate_group, *remainder]
            return None

        return _search(0, 0)

    def _copy_targeted_spell(
        self,
        game: GameState,
        controller: Player,
        original: StackObject,
    ) -> None:
        copied_targets = self._choose_new_targets_for_copy(game, controller, original)
        game.stack.push(copy_spell(game, original, controller, copied_targets))

    def _register_token_sacrifice(self, game: GameState, token: Creature) -> None:
        controller = token.controller
        if controller is None:
            return
        delayed_source = object()

        def _condition(_game: GameState, _event: EndStepTriggeredEvent) -> bool:
            return any(_game.get_battlefield(player).contains(token) for player in _game.players)

        def _effect(g: GameState) -> None:
            token_controller = getattr(token, "controller", None)
            if token_controller is not None and g.get_battlefield(token_controller).contains(token):
                sacrifice(g, token_controller, token)
            g.trigger_manager.unregister(delayed_source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )

    def _copy_creature_spell(
        self,
        game: GameState,
        controller: Player,
        original: StackObject,
    ) -> None:
        copied_spell = copy.copy(original.source)
        copied_spell.controller = controller
        copied_spell.owner = getattr(original.source, "owner", controller)
        copy_obj = StackObject(source=copied_spell, controller=controller, is_spell=True)

        def _resolve_copy(g: GameState) -> None:
            token = copy.copy(copied_spell)
            token.controller = controller
            token.owner = copied_spell.owner
            token.is_token = True
            token.keywords |= Keyword.HASTE
            if hasattr(token, "summoning_sick"):
                token.summoning_sick = False
            token.snapshot_current_characteristics()
            g.get_battlefield(controller).add(token)
            self._register_token_sacrifice(g, token)

        copy_obj.on_resolve = _resolve_copy
        game.stack.push(copy_obj)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        for target in getattr(self, "chosen_targets", []):
            if not isinstance(target, StackObject) or not bool(getattr(target, "is_spell", False)):
                continue
            if isinstance(getattr(target, "source", None), (Instant, Sorcery)):
                self._copy_targeted_spell(game, controller, target)
            elif isinstance(getattr(target, "source", None), Creature):
                self._copy_creature_spell(game, controller, target)
