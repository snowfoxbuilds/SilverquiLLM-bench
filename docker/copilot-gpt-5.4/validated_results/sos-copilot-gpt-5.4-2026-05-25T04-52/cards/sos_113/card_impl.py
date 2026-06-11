"""Card implementation for Emeritus of Conflict // Lightning Bolt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LightningBolt(Instant):
    """Prepared spell copy for Emeritus of Conflict."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lightning Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature) or hasattr(obj, "life"),
                description="target creature or player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if target is None:
            return
        deal_damage(game, self, target, 3)


class EmeritusOfConflictLightningBolt(Creature):
    """Emeritus of Conflict."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Conflict")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._spells_cast_this_turn = 0
        self._spells_cast_turn_number: int | None = None

    def create_prepared_spell_copy(self) -> Instant:
        return LightningBolt(owner=self.owner, controller=self.controller)

    def _note_spell_cast(self, game: GameState) -> bool:
        if self._spells_cast_turn_number != game.turn_number:
            self._spells_cast_turn_number = game.turn_number
            self._spells_cast_this_turn = 0
        self._spells_cast_this_turn += 1
        return self._spells_cast_this_turn == 3

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            return source._note_spell_cast(game)

        def _effect(game: GameState) -> None:
            if source.is_on_battlefield(game):
                source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
