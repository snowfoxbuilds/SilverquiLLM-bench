"""Card implementation for Arnyn, Deathbloom Botanist."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    CreatureDiesTriggeredEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArnynDeathbloomBotanist(Creature):
    """Arnyn, Deathbloom Botanist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arnyn, Deathbloom Botanist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Vampire", "Druid"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Deathtouch\nWhenever a creature you control with power or toughness 1 or less dies, "
            "target opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player
        queued_triggers: deque[tuple[Player, Player]] = deque()
        opponent_requirement = TargetRequirement(
            filter_fn=lambda obj: isinstance(obj, Player),
            description="target opponent",
            zone=Zone.BATTLEFIELD,
        )

        def _condition(game: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            creature = event.creature
            if current_controller is None or event.controller is not current_controller:
                return False
            if creature is None:
                return False
            return getattr(creature, "power", 0) <= 1 or getattr(creature, "toughness", 0) <= 1

        def _effect(game: GameState) -> None:
            triggering_controller, target = queued_triggers.popleft() if queued_triggers else (None, None)
            if triggering_controller is None or target is None:
                return
            if target not in game.players or target is triggering_controller:
                return

            target.life -= 2
            triggering_controller.life += 2
            game.trigger_manager.fire_event(game, LosesLifeTriggeredEvent(player=target, amount=2))
            game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=triggering_controller, amount=2))

        def _queue_target(game: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            if not _condition(game, event):
                return False
            triggering_controller = getattr(source, "controller", None)
            if triggering_controller is None:
                return False
            opponents = [player for player in game.players if player is not triggering_controller]
            if not opponents:
                return False
            target = triggering_controller.choose_target(opponents, opponent_requirement)
            if target not in opponents:
                return False
            queued_triggers.append((triggering_controller, target))
            return True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CreatureDiesTriggeredEvent,
                condition=_queue_target,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
