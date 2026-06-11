"""Card implementation for Aziza, Mage Tower Captain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.casting import (
    _fire_becomes_target_events,
    _normalize_chosen_targets,
    _queue_ward_triggers,
)
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject, copy_spell
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype, TargetRequirement

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AzizaMageTowerCaptain(Creature):
    """Aziza, Mage Tower Captain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aziza, Mage Tower Captain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Djinn", "Sorcerer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

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

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
                and source.is_on_battlefield(g)
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
                    should_copy = locked_controller.choose_yes_no(
                        "Tap three untapped creatures you control to copy that spell?"
                    )
                except Exception:
                    should_copy = False
                if not should_copy:
                    return

                untapped_creatures = [
                    permanent
                    for permanent in game_at_resolution.get_battlefield(locked_controller).get_all()
                    if (
                        isinstance(permanent, Creature)
                        and not getattr(permanent, "is_tapped", False)
                    )
                ]
                if len(untapped_creatures) < 3:
                    return

                chosen_creatures: list[Creature] = []
                remaining = list(untapped_creatures)
                try:
                    for _ in range(3):
                        chosen = locked_controller.choose_card(
                            list(remaining),
                            "Choose an untapped creature to tap for Aziza",
                        )
                        if chosen not in remaining:
                            return
                        chosen_creatures.append(chosen)
                        remaining.remove(chosen)
                except Exception:
                    return

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

                for creature in chosen_creatures:
                    creature.is_tapped = True

                new_targets = self._choose_new_targets_for_copy(
                    game_at_resolution,
                    locked_controller,
                    original_stack_obj,
                )
                copied_spell = copy_spell(
                    game_at_resolution,
                    original_stack_obj,
                    locked_controller,
                    new_targets,
                )
                game_at_resolution.stack.push(copied_spell)
                _fire_becomes_target_events(
                    game_at_resolution,
                    locked_controller,
                    copied_spell.source,
                    copied_spell,
                    copied_spell.targets,
                )
                _queue_ward_triggers(
                    game_at_resolution,
                    locked_controller,
                    copied_spell.source,
                    copied_spell,
                    copied_spell.targets,
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
