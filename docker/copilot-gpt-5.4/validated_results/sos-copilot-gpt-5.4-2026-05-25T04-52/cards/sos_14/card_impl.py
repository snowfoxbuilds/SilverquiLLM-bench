"""Card implementation for Ennis, Debate Moderator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EnnisDebateModerator(Creature):
    """Ennis, Debate Moderator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ennis, Debate Moderator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When Ennis enters, exile up to one other target creature you control. Return that card "
            "to the battlefield under its owner's control at the beginning of the next end step.\n"
            "At the beginning of your end step, if one or more cards were put into exile this turn, "
            "put a +1/+1 counter on Ennis.",
        )
        super().__init__(**kwargs)
        self._cards_to_return_at_end_step: list[Creature] = []

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature)
                and obj is not self
                and getattr(obj, "controller", None) is self.controller,
                description="up to one other target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, Creature):
            return
        controller = self.controller
        if controller is None:
            return
        if target is self or getattr(target, "controller", None) is not controller:
            return
        if not game.get_battlefield(controller).contains(target):
            return

        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
        self._cards_to_return_at_end_step.append(target)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _return_condition(game: GameState, event: EndStepTriggeredEvent) -> bool:  # noqa: ARG001
            return bool(source._cards_to_return_at_end_step)

        def _return_effect(game: GameState) -> None:
            pending = list(source._cards_to_return_at_end_step)
            source._cards_to_return_at_end_step.clear()
            for card in pending:
                owner = getattr(card, "owner", None)
                if owner is None or not game.get_exile(owner).contains(card):
                    continue
                card.controller = owner
                move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)

        def _counter_condition(game: GameState, event: EndStepTriggeredEvent) -> bool:
            return event.player is source.controller and bool(game.cards_exiled_this_turn)

        def _counter_effect(game: GameState) -> None:  # noqa: ARG001
            source.plus_one_counters += 1
            source._base_plus_one_counters = source.plus_one_counters

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_return_condition,
                effect=_return_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_counter_condition,
                effect=_counter_effect,
                source=self,
                controller=controller,
            )
        )
