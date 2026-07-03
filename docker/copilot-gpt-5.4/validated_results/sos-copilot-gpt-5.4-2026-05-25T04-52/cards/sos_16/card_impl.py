"""Card implementation for Graduation Day."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GraduationDay(Enchantment):
    """Graduation Day."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Graduation Day")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Repartee — Whenever you cast an instant or sorcery spell that targets a creature, "
            "put a +1/+1 counter on target creature you control.",
        )
        super().__init__(**kwargs)

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
            if current_controller is None:
                return
            candidates = [
                permanent
                for permanent in game.get_battlefield(current_controller).get_all()
                if isinstance(permanent, Creature) and getattr(permanent, "controller", None) is current_controller
            ]
            if not candidates:
                return
            target = current_controller.choose_card(candidates, "Choose target creature you control")
            if not isinstance(target, Creature):
                return
            if not game.get_battlefield(current_controller).contains(target):
                return
            target.plus_one_counters += 1
            target._base_plus_one_counters = target.plus_one_counters

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
