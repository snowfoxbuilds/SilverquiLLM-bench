"""Card implementation for Topiary Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, ManaAbility
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TopiaryLecturer(Creature):
    """Topiary Lecturer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Topiary Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        if any(
            trigger.event_type is SpellCastTriggeredEvent
            for trigger in game.trigger_manager.get_triggers_for_source(self)
        ):
            return

        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            if not source.is_on_battlefield(g):
                return False
            mana_spent = int(getattr(event.spell, "mana_spent", 0))
            return mana_spent > source.power or mana_spent > source.toughness

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                add_counter(g, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(_game: GameState, card: Creature) -> bool:
            if card.is_tapped:
                return False
            card.is_tapped = True
            return True

        def _mana_produced(_game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            controller.mana_pool.add(ManaType.GREEN, max(0, source.power))

        return [
            ManaAbility(
                cost=_cost,
                mana_produced=_mana_produced,
                description="{T}: Add an amount of {G} equal to this creature's power.",
            )
        ]
