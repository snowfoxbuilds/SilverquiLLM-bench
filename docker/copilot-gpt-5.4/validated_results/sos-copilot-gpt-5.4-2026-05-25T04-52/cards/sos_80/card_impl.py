"""Card implementation for Emeritus of Woe // Demonic Tutor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DemonicTutor(Sorcery):
    """Prepared spell copy for Emeritus of Woe."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Demonic Tutor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        choices = library.get_all()
        if not choices:
            return
        try:
            chosen = controller.choose_card(choices, "card to put into your hand")
        except Exception:
            chosen = choices[0]
        if chosen is None or not library.contains(chosen):
            return
        library.remove(chosen)
        game.get_hand(controller).add(chosen)
        library.shuffle()


class EmeritusOfWoeDemonicTutor(Creature):
    """Emeritus of Woe."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Woe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "This creature enters prepared.\nAt the beginning of your end step, if two "
            "or more creatures died this turn, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return DemonicTutor(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _end_step_condition(game: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and len(getattr(game, "creatures_died_this_turn", [])) >= 2
            )

        def _prepare(game: GameState) -> None:  # noqa: ARG001
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_end_step_condition,
                effect=_prepare,
                source=self,
                controller=controller,
            )
        )
