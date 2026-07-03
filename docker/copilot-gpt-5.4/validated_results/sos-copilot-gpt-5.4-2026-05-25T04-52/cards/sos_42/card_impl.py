"""Card implementation for Deluge Virtuoso."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, tap
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DelugeVirtuoso(Creature):
    """Deluge Virtuoso."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Deluge Virtuoso")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._pending_opus_bonuses: list[int] = []
        self._queue_etb_trigger_on_entry = False

    def _etb_target_requirement(self) -> TargetRequirement:
        controller = self.controller
        return TargetRequirement(
            filter_fn=lambda obj, _controller=controller: (
                isinstance(obj, Creature)
                and getattr(obj, "controller", None) is not None
                and getattr(obj, "controller", None) is not _controller
            ),
            description="target creature an opponent controls",
            zone=Zone.BATTLEFIELD,
        )

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                return []
        return [self._etb_target_requirement()]

    def on_resolve(self, game: GameState) -> None:
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                self._queue_etb_trigger_on_entry = True
                return
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        if not isinstance(target, Creature) or not target.is_on_battlefield(game):
            return
        tap(game, target)
        add_counter(game, target, "stun", 1)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        if (
            source.controller is not None
            and game.get_battlefield(source.controller).contains(source)
            and source._queue_etb_trigger_on_entry
        ):
            source._queue_etb_trigger_on_entry = False
            def _etb_effect(game: GameState) -> None:
                current_controller = getattr(source, "controller", None)
                if current_controller is None or not source.is_on_battlefield(game):
                    return
                requirement = source._etb_target_requirement()
                candidates = [
                    permanent
                    for player in game.players
                    for permanent in game.get_battlefield(player).get_all()
                    if requirement.filter_fn(permanent)
                ]
                if not candidates:
                    return
                target = None
                try:
                    target = current_controller.choose_target([requirement], requirement)
                except Exception:
                    target = None
                if target not in candidates:
                    target = candidates[0]
                tap(game, target)
                add_counter(game, target, "stun", 1)

            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_etb_effect,
                )
            )

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            matches = (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            )
            if matches:
                mana_spent = getattr(spell, "mana_spent", 0)
                source._pending_opus_bonuses.append(2 if mana_spent >= 5 else 1)
            return matches

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                if source._pending_opus_bonuses:
                    source._pending_opus_bonuses.pop()
                return
            bonus = source._pending_opus_bonuses.pop() if source._pending_opus_bonuses else 1

            def _apply(_game: GameState) -> None:
                source.modified_power += bonus
                source.modified_toughness += bonus

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
