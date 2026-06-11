"""Card implementation for Paradox Surveyor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Land
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.game import (
    look_at_cards,
    put_cards_on_bottom_in_random_order,
    reveal_cards,
)
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _has_x_in_mana_cost(card: Any) -> bool:
    mana_cost = getattr(card, "mana_cost", None)
    return bool(mana_cost is not None and getattr(mana_cost, "x_count", 0) > 0)


class ParadoxSurveyor(Creature):
    """Paradox Surveyor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Paradox Surveyor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{G/U}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return getattr(event, "permanent", None) is source and source.is_on_battlefield(g)

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            library = g.get_library(current_controller)
            looked_at = list(library.top(5))
            if not looked_at:
                return
            look_at_cards(g, current_controller, looked_at, source=source, reason=source.name)
            eligible = [card for card in looked_at if isinstance(card, Land) or _has_x_in_mana_cost(card)]
            chosen = None
            if eligible:
                chosen = current_controller.choose_card(
                    list(eligible),
                    "Choose a land card or a card with {X} in its mana cost",
                )
                if chosen not in eligible:
                    chosen = None
            if chosen is not None:
                reveal_cards(g, current_controller, [chosen], source=source, reason=source.name)
                move_to_zone(g, chosen, Zone.LIBRARY, Zone.HAND)
            remaining = [card for card in looked_at if card is not chosen]
            if remaining:
                put_cards_on_bottom_in_random_order(
                    g,
                    current_controller,
                    remaining,
                    source=source,
                    reason=source.name,
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
