"""Card implementation for Environmental Scientist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.game import reveal_cards, shuffle_library
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EnvironmentalScientist(Creature):
    """Environmental Scientist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Environmental Scientist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Human", "Druid"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source and source.is_on_battlefield(g)

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            if not current_controller.choose_yes_no("Search your library for a basic land card?"):
                return
            library = g.get_library(current_controller)
            basics = [
                card
                for card in library.get_all()
                if CardType.LAND in getattr(card, "card_types", set())
                and Supertype.BASIC in getattr(card, "supertypes", set())
            ]
            chosen = None
            if basics:
                chosen = current_controller.choose_card(basics, "Choose a basic land card")
            if chosen in basics:
                reveal_cards(
                    g,
                    current_controller,
                    [chosen],
                    source=source,
                    reason="Environmental Scientist enters",
                )
                move_to_zone(g, chosen, Zone.LIBRARY, Zone.HAND)
            shuffle_library(
                g,
                current_controller,
                source=source,
                reason="Environmental Scientist search",
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
