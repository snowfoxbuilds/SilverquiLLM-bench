"""Card implementation for Mica, Reader of Ruins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.casting import _normalize_chosen_targets
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import sacrifice
from benchmarks.sos.workspace.engine.stack import StackObject, copy_spell
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MicaReaderOfRuins(Creature):
    """Mica, Reader of Ruins."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mica, Reader of Ruins")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Human", "Artificer"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.ward_cost = 3

    def _choose_new_targets_for_copy(
        self,
        game: GameState,
        controller: Any,
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
            if not chosen_group:
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

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            original_spell = getattr(event, "spell", None)
            if current_controller is None or original_spell is None:
                return None

            def _resolve(game_at_resolution: GameState, *, locked_controller=current_controller, spell=original_spell) -> None:
                try:
                    should_sacrifice = locked_controller.choose_yes_no(
                        "Sacrifice an artifact to copy this spell?"
                    )
                except Exception:
                    should_sacrifice = False
                if not should_sacrifice:
                    return
                artifacts = [
                    permanent
                    for permanent in game_at_resolution.get_battlefield(locked_controller).get_all()
                    if CardType.ARTIFACT in getattr(permanent, "card_types", set())
                ]
                if not artifacts:
                    return
                try:
                    chosen_artifact = locked_controller.choose_card(
                        artifacts,
                        "Choose an artifact to sacrifice",
                    )
                except Exception:
                    chosen_artifact = artifacts[0]
                if chosen_artifact not in artifacts:
                    chosen_artifact = artifacts[0]
                sacrifice(game_at_resolution, locked_controller, chosen_artifact)

                original_stack_obj = next(
                    (
                        stack_obj
                        for stack_obj in reversed(game_at_resolution.stack.objects())
                        if getattr(stack_obj, "source", None) is spell
                    ),
                    None,
                )
                if original_stack_obj is None:
                    return
                new_targets = self._choose_new_targets_for_copy(
                    game_at_resolution,
                    locked_controller,
                    original_stack_obj,
                )
                game_at_resolution.stack.push(
                    copy_spell(game_at_resolution, original_stack_obj, locked_controller, new_targets)
                )

            return StackObject(
                source=source,
                controller=current_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
