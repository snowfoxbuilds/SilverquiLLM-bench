"""Card implementation for Magmablood Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Color, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MagmabloodArchaic(Creature):
    """Magmablood Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Magmablood Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2/R}{2/R}{2/R}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        colors_spent = {
            color for color in getattr(self, "colors_spent", []) if isinstance(color, Color)
        }
        if colors_spent:
            add_counter(game, self, "+1/+1", len(colors_spent))

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
            bonus = len(
                {color for color in getattr(spell, "colors_spent", []) if isinstance(color, Color)}
            )
            if bonus <= 0:
                bonus = 0

            def _resolve(game_at_resolution: GameState, *, locked_controller=controller, amount: int = bonus) -> None:
                if amount <= 0:
                    return
                game_at_resolution.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=lambda g, player=locked_controller, power_bonus=amount: [
                            setattr(
                                creature,
                                "modified_power",
                                creature.modified_power + power_bonus,
                            )
                            for creature in g.get_battlefield(player).get_all()
                            if isinstance(creature, Creature)
                        ],
                        duration=DURATION_END_OF_TURN,
                    )
                )
                game_at_resolution.effect_manager.apply_all(game_at_resolution)

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
