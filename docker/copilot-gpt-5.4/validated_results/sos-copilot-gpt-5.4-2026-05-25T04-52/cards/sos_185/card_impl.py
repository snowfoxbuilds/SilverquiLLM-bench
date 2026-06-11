"""Card implementation for Elemental Mascot."""

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
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ElementalMascot(Creature):
    """Elemental Mascot."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elemental Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{R}"))
        kwargs.setdefault("subtypes", {"Elemental", "Bird"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self._pending_opus_big_spells: list[bool] = []

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if (
                current_controller is None
                or event.player is not current_controller
                or spell is None
                or not source.is_on_battlefield(g)
                or not bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            ):
                return False
            source._pending_opus_big_spells.append(int(getattr(spell, "mana_spent", 0)) >= 5)
            return True

        def _effect(g: GameState) -> None:
            big_spell = source._pending_opus_big_spells.pop() if source._pending_opus_big_spells else False
            if not source.is_on_battlefield(g):
                return

            def _apply(_game: GameState) -> None:
                source.modified_power += 1

            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            g.effect_manager.apply_all(g)

            if not big_spell:
                return
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            library = g.get_library(current_controller)
            top_cards = library.top(1)
            if not top_cards:
                return
            exiled = top_cards[0]
            move_to_zone(g, exiled, Zone.LIBRARY, Zone.EXILE)
            g.grant_exile_play_permission_until_end_of_next_turn(
                current_controller,
                exiled,
                source=source,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
