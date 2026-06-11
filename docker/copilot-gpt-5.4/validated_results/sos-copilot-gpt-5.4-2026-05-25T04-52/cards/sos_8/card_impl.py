"""Card implementation for Ascendant Dustspeaker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent
from benchmarks.sos.workspace.engine.game import exile
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AscendantDustspeaker(Creature):
    """Ascendant Dustspeaker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ascendant Dustspeaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault("subtypes", {"Orc", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, put a +1/+1 counter on another target "
            "creature you control.\nAt the beginning of combat on your turn, exile up to "
            "one target card from a graveyard.",
        )
        super().__init__(**kwargs)

    def _apply_counter_to_target(self, target: Creature | None) -> None:
        if target is None or target is self:
            return
        if not isinstance(target, Creature):
            return
        if getattr(target, "controller", None) is not self.controller:
            return
        target.plus_one_counters += 1
        if hasattr(target, "_base_plus_one_counters"):
            target._base_plus_one_counters = target.plus_one_counters

    def on_resolve(self, game: GameState) -> None:
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                return
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        self._apply_counter_to_target(target)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        if source.controller is not None and game.get_battlefield(source.controller).contains(source):
            def _etb_effect(game: GameState) -> None:
                current_controller = source.controller
                if current_controller is None:
                    return
                candidates = [
                    permanent
                    for permanent in game.get_battlefield(current_controller).get_all()
                    if isinstance(permanent, Creature)
                    and permanent is not source
                    and getattr(permanent, "controller", None) is current_controller
                ]
                if not candidates:
                    return
                choice = current_controller.choose_card(
                    candidates,
                    "Choose another creature you control for Ascendant Dustspeaker",
                )
                source._apply_counter_to_target(choice)

            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_etb_effect,
                )
            )

        def _condition(game: GameState, event: BeginningOfCombatTriggeredEvent) -> bool:
            return source.controller is not None and game.active_player is source.controller

        def _effect(game: GameState) -> None:
            current_controller = source.controller
            if current_controller is None:
                return
            candidates = []
            for player in game.players:
                candidates.extend(game.get_graveyard(player).get_all())
            if not candidates:
                return
            choice = current_controller.choose_card(
                candidates + [None],
                "Choose up to one card from a graveyard to exile",
            )
            if choice is None:
                return
            exile(game, choice)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfCombatTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
