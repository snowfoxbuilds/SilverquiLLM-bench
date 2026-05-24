"""Card implementation for Infernal Vessel."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from cards.registry import CardRegistry

class InfernalVessel(Creature):
    """Infernal Vessel — {2}{B} — 2/1 — Human Cleric

    When this creature dies, if it wasn't a Demon, return it to the
    battlefield under its owner's control with two +1/+1 counters on
    it. It's a Demon in addition to its other types.

    FDN collector number 63.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Infernal Vessel')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}'))
        kwargs.setdefault('subtypes', {'Human', 'Cleric'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', "When this creature dies, if it wasn't a Demon, return it to the battlefield under its owner's control with two +1/+1 counters on it. It's a Demon in addition to its other types.")
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        from benchmarks.sos.workspace.engine.game import add_counter
        source = self

        def _condition(game: Any, event: dict) -> bool:
            creature = event.creature
            if creature is not source:
                return False
            subtypes = getattr(creature, 'subtypes', set())
            return 'Demon' not in subtypes

        def _effect(game: GameState) -> None:
            owner = getattr(source, 'owner', None)
            if owner is None:
                return
            subtypes = getattr(source, 'subtypes', set())
            source.subtypes = subtypes | {'Demon'}
            source.controller = owner
            graveyard = owner.zones[Zone.GRAVEYARD]
            if graveyard.contains(source):
                move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)
                add_counter(game, source, '+1/+1', 2)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
