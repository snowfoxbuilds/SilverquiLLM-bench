# UNVERIFIED: Secret Rendezvous spell-face behavior is not specified in card_spec.json — resolution text missing
"""Card implementation for Joined Researchers // Secret Rendezvous."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SecretRendezvous(Sorcery):
    """Prepared spell copy placeholder for Joined Researchers."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Secret Rendezvous")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        super().__init__(**kwargs)


class JoinedResearchersSecretRendezvous(Creature):
    """Joined Researchers."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Joined Researchers")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "First strike\nAt the beginning of each end step, if an opponent has more cards in "
            "hand than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is None or event.player is current_controller:
                return False
            return len(game.get_hand(event.player).get_all()) > len(game.get_hand(current_controller).get_all())

        def _effect(game: GameState) -> None:  # noqa: ARG001
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def create_prepared_spell_copy(self) -> Sorcery:
        return SecretRendezvous(owner=self.owner, controller=self.controller)
