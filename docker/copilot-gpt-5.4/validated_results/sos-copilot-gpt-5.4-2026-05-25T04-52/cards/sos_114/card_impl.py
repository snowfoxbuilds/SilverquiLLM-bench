"""Card implementation for Expressive Firedancer."""

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
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ExpressiveFiredancer(Creature):
    """Expressive Firedancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Expressive Firedancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Sorcerer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._pending_opus_double_strike: list[bool] = []

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if (
                current_controller is None
                or event.player is not current_controller
                or spell is None
                or not bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            ):
                return False
            source._pending_opus_double_strike.append(getattr(spell, "mana_spent", 0) >= 5)
            return True

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                if source._pending_opus_double_strike:
                    source._pending_opus_double_strike.pop()
                return
            grant_double_strike = (
                source._pending_opus_double_strike.pop() if source._pending_opus_double_strike else False
            )

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=lambda _game: (
                        setattr(source, "modified_power", source.modified_power + 1),
                        setattr(source, "modified_toughness", source.modified_toughness + 1),
                    ),
                    duration=DURATION_END_OF_TURN,
                )
            )
            if grant_double_strike:
                game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.ABILITY,
                        apply=lambda _game: setattr(
                            source,
                            "keywords",
                            source.keywords | Keyword.DOUBLE_STRIKE,
                        ),
                        duration=DURATION_END_OF_TURN,
                    )
                )
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
