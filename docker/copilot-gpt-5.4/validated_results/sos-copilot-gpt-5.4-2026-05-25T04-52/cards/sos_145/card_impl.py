"""Card implementation for Emeritus of Abundance // Regrowth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Regrowth(Sorcery):
    """Prepared spell copy for Emeritus of Abundance."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Regrowth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, _controller=controller: getattr(obj, "owner", None) is _controller,
                description="target card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        target = getattr(self, "chosen_targets", [None])[0]
        if controller is None or target is None:
            return
        if not game.get_graveyard(controller).contains(target):
            return
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)


class EmeritusOfAbundanceRegrowth(Creature):
    """Emeritus of Abundance."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Abundance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return Regrowth(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: AttacksTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.creature is not source:
                return False
            lands_controlled = sum(
                1
                for permanent in g.get_battlefield(current_controller).get_all()
                if isinstance(permanent, Land)
            )
            return lands_controlled >= 8

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
