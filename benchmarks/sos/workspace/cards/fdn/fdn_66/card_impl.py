"""Card implementation for Nine-Lives Familiar."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.events import CreatureDiesTriggeredEvent, EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

class NineLivesFamiliar(Creature):
    """Nine-Lives Familiar — {1}{B}{B} — 1/1 — Cat

    This creature enters with eight revival counters on it if you cast it.
    When this creature dies, if it had a revival counter on it, return it
    to the battlefield with one fewer revival counter on it at the
    beginning of the next end step.

    FDN collector number 66.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Nine-Lives Familiar')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{B}'))
        kwargs.setdefault('subtypes', {'Cat'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'This creature enters with eight revival counters on it if you cast it.\nWhen this creature dies, if it had a revival counter on it, return it to the battlefield with one fewer revival counter on it at the beginning of the next end step.')
        super().__init__(**kwargs)
        self.revival_counters: int = 0

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone
        source = self

        def _etb_condition(game: Any, event: dict) -> bool:
            return event.permanent is source

        def _etb_effect(game: GameState) -> None:
            if getattr(source, '_returning_from_graveyard', False):
                source._returning_from_graveyard = False
                return
            source.revival_counters = 8

        def _dies_condition(game: Any, event: dict) -> bool:
            creature = event.creature
            if creature is not source:
                return False
            return source.revival_counters > 0

        def _dies_effect(game: GameState) -> None:
            owner = getattr(source, 'owner', None)
            if owner is None:
                return
            new_counters = source.revival_counters - 1
            source.controller = owner
            graveyard = owner.zones[Zone.GRAVEYARD]
            if graveyard.contains(source):
                source._returning_from_graveyard = True
                source.revival_counters = new_counters
                move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_etb_condition, effect=_etb_effect, source=self, controller=controller))
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_dies_condition, effect=_dies_effect, source=self, controller=controller))
