"""Card implementation for Scheming Silvertongue // Sign in Blood."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Phase

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SignInBlood(Sorcery):
    """Prepared spell copy for Scheming Silvertongue."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sign in Blood")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class SchemingSilvertongueSignInBlood(Creature):
    """Scheming Silvertongue."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scheming Silvertongue")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying, lifelink\nAt the beginning of your second main phase, if you gained 2 or more life "
            "this turn, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Sorcery:
        return SignInBlood(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and event.phase == Phase.POSTCOMBAT_MAIN
                and getattr(current_controller, "life_gained_this_turn", 0) >= 2
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
