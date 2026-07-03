"""Card implementation for Inkling Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_repartee_spell(game: GameState, source: Creature, event: SpellCastTriggeredEvent) -> bool:
    current_controller = getattr(source, "controller", None)
    if current_controller is None or event.player is not current_controller:
        return False
    if not source.is_on_battlefield(game):
        return False
    spell = getattr(event, "spell", None)
    if spell is None:
        return False
    card_types = getattr(spell, "card_types", set())
    if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
        return False
    return any(
        isinstance(target, Creature) and target.is_on_battlefield(game)
        for target in getattr(spell, "_casting_targets", [])
    )


class InklingMascot(Creature):
    """Inkling Mascot."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inkling Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
        kwargs.setdefault("subtypes", {"Inkling", "Cat"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            return _is_repartee_spell(g, source, event)

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(g):
                return

            def _grant_flying(_game: GameState, *, creature: Creature = source) -> None:
                if creature.is_on_battlefield(_game):
                    creature.keywords |= Keyword.FLYING

            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=_grant_flying,
                    duration=DURATION_END_OF_TURN,
                )
            )
            g.effect_manager.apply_all(g)

            top_card = g.get_library(current_controller).top(1)
            if not top_card:
                return
            if current_controller.choose_yes_no("Put the surveilled card into your graveyard?"):
                move_to_zone(g, top_card[0], Zone.LIBRARY, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
