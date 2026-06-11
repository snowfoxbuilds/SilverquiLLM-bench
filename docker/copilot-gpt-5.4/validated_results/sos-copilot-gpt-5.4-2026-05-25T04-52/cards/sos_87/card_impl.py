"""Card implementation for Lecturing Scornmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_repartee_spell(game: GameState, source: Creature, event: SpellCastTriggeredEvent) -> bool:
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


class LecturingScornmage(Creature):
    """Lecturing Scornmage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lecturing Scornmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Repartee — Whenever you cast an instant or sorcery spell that targets a creature, "
            "put a +1/+1 counter on this creature.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            return _is_repartee_spell(game, source, event)

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                return
            add_counter(game, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
