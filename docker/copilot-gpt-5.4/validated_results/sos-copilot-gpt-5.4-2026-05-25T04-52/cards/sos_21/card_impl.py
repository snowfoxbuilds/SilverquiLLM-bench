"""Card implementation for Inkshape Demonstrator."""

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


class InkshapeDemonstrator(Creature):
    """Inkshape Demonstrator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inkshape Demonstrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Elephant", "Cleric"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Ward {2}\nRepartee — Whenever you cast an instant or sorcery spell that targets a "
            "creature, this creature gets +1/+0 and gains lifelink until end of turn.",
        )
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{2}")

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            spell = event.spell
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            return any(
                isinstance(target, Creature) and target.is_on_battlefield(game)
                for target in getattr(spell, "_casting_targets", [])
            )

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(game):
                return

            def _apply_power(game: GameState) -> None:  # noqa: ARG001
                source.modified_power += 1

            def _apply_lifelink(game: GameState) -> None:  # noqa: ARG001
                source.keywords |= Keyword.LIFELINK

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_power,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=_apply_lifelink,
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
