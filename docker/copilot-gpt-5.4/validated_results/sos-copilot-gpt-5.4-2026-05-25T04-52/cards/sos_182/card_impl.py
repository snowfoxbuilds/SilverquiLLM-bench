"""Card implementation for Conciliator's Duelist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    SpellCastTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.protection import get_illegal_target_reason
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ConciliatorsDuelist(Creature):
    """Conciliator's Duelist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Conciliator's Duelist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{W}{B}{B}"))
        kwargs.setdefault("subtypes", {"Kor", "Warlock"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self._pending_returns: list[Creature] = []
        self._return_trigger_registered = False

    def _register_return_trigger(self, game: GameState) -> None:
        if self._return_trigger_registered:
            return
        self._return_trigger_registered = True
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_g: GameState, event: EndStepTriggeredEvent) -> bool:  # noqa: ARG001
            return bool(source._pending_returns)

        def _effect(g: GameState) -> None:
            pending = list(source._pending_returns)
            source._pending_returns.clear()
            for card in pending:
                owner = getattr(card, "original_owner", None) or getattr(card, "owner", None)
                if owner is None or not g.get_exile(owner).contains(card):
                    continue
                card.owner = owner
                card.controller = owner
                move_to_zone(g, card, Zone.EXILE, Zone.BATTLEFIELD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _is_battlefield_creature(g: GameState, target: object) -> bool:
            return isinstance(target, Creature) and target.is_on_battlefield(g)

        def _enters_condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source and source.is_on_battlefield(g)

        def _enters_effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            draw_card(g, current_controller)
            for player in g.players:
                player.life -= 1

        def _repartee_condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            chosen_targets = list(getattr(spell, "_casting_targets", []))
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and source.is_on_battlefield(g)
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
                and any(_is_battlefield_creature(g, target) for target in chosen_targets)
            )

        def _repartee_effect(_g: GameState) -> None:
            return

        def _create_repartee_stack_object(g: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None

            target_requirement = TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
            )
            target_requirement.min_targets = 0  # type: ignore[attr-defined]
            target_requirement.max_targets = 1  # type: ignore[attr-defined]

            candidates = [
                permanent
                for player in g.players
                for permanent in g.get_battlefield(player).get_all()
                if _is_battlefield_creature(g, permanent)
                and get_illegal_target_reason(permanent, source) is None
            ]
            chosen: Creature | None = None
            if candidates:
                try:
                    chosen = current_controller.choose_target([target_requirement], target_requirement)
                except Exception:
                    chosen = candidates[0]
                if chosen is not None and chosen not in candidates:
                    chosen = candidates[0]

            def _resolve(game_at_resolution: GameState, *, target: Creature | None = chosen) -> None:
                if current_controller is None or not source.is_on_battlefield(game_at_resolution) or target is None:
                    return
                if not _is_battlefield_creature(game_at_resolution, target):
                    return
                if get_illegal_target_reason(target, source) is not None:
                    return
                original_owner = getattr(target, "original_owner", None)
                if original_owner is not None:
                    target.owner = original_owner
                move_to_zone(game_at_resolution, target, Zone.BATTLEFIELD, Zone.EXILE)
                source._pending_returns.append(target)
                source._register_return_trigger(game_at_resolution)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[] if chosen is None else [chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_enters_condition,
                effect=_enters_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_repartee_condition,
                effect=_repartee_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_repartee_stack_object,
            )
        )
