"""Card implementation for Thunderdrum Soloist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ThunderdrumSoloist(Creature):
    """Thunderdrum Soloist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thunderdrum Soloist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Bard"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if current_controller is None or spell is None:
                return None
            damage = 3 if getattr(spell, "mana_spent", 0) >= 5 else 1

            def _resolve(game_at_resolution: GameState, *, amount: int = damage) -> None:
                if not source.is_on_battlefield(game_at_resolution):
                    return
                for player in game_at_resolution.players:
                    if player is not current_controller:
                        deal_damage(game_at_resolution, source, player, amount)

            return StackObject(
                source=source,
                controller=current_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
