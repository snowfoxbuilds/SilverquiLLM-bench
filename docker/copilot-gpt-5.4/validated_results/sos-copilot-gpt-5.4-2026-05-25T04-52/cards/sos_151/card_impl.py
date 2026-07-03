"""Card implementation for Hungry Graffalon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HungryGraffalon(Creature):
    """Hungry Graffalon."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hungry Graffalon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Giraffe"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            mana_spent = getattr(spell, "mana_spent", 0)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and (mana_spent > source.power or mana_spent > source.toughness)
            )

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
