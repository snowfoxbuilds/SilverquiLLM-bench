"""Card implementation for Wildgrowth Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Color, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class WildgrowthArchaic(Creature):
    """Wildgrowth Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wildgrowth Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2/G}{2/G}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        colors_spent = {
            color for color in getattr(self, "colors_spent", []) if isinstance(color, Color)
        }
        if colors_spent:
            add_counter(game, self, "+1/+1", len(colors_spent))

    def register_triggers(self, game: GameState) -> None:
        if any(
            trigger.event_type is SpellCastTriggeredEvent
            for trigger in game.trigger_manager.get_triggers_for_source(self)
        ):
            return

        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and spell is not None
                and CardType.CREATURE in getattr(spell, "card_types", set())
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if current_controller is None or spell is None:
                return None
            counter_count = len(
                {color for color in getattr(spell, "colors_spent", []) if isinstance(color, Color)}
            )

            def _resolve(game_at_resolution: GameState, *, target=spell, amount: int = counter_count) -> None:
                if amount <= 0:
                    return
                if not any(player.zones[Zone.STACK].contains(target) for player in game_at_resolution.players):
                    return
                if not any(stack_item.source is target for stack_item in game_at_resolution.stack.objects()):
                    return
                add_counter(game_at_resolution, target, "+1/+1", amount)

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
