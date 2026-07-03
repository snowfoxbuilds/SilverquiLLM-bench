"""Card implementation for Textbook Tabulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TextbookTabulator(Creature):
    """Textbook Tabulator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Textbook Tabulator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Frog", "Wizard"})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Increment\nWhen this creature enters, surveil 2.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        for card in reversed(library.top(2)):
            if controller.choose_yes_no(
                f"Put {getattr(card, 'name', 'this card')} into your graveyard?"
            ):
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _increment_condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            if not source.is_on_battlefield(game):
                return False
            mana_spent = int(getattr(event.spell, "mana_spent", 0))
            return mana_spent > source.power or mana_spent > source.toughness

        def _increment_effect(game: GameState) -> None:
            if source.is_on_battlefield(game):
                add_counter(game, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_increment_condition,
                effect=_increment_effect,
                source=self,
                controller=controller,
            )
        )
