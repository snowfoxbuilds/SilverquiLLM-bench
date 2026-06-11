"""Card implementation for Blech, Loafing Pest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


_SUPPORTED_SUBTYPES = frozenset({"Pest", "Bat", "Insect", "Snake", "Spider"})


class BlechLoafingPest(Creature):
    """Blech, Loafing Pest."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blech, Loafing Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Pest"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GainsLifeTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for permanent in g.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature) and permanent.subtypes & _SUPPORTED_SUBTYPES:
                    add_counter(g, permanent, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GainsLifeTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
