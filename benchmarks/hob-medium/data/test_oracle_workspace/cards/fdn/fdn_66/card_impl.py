"""Card implementation for Nine-Lives Familiar."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.events import CreatureDiesTriggeredEvent
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

    def enters_battlefield_with(self, game: GameState, event: Any) -> None:
        """Enters with eight revival counters if you cast it (rule 614.1c).

        "If you cast it" — the creature entering from the stack, i.e. a resolved
        cast. A return via the dies-trigger enters from the graveyard and gets
        no fresh revival counters (it keeps the one-fewer count it left with),
        so the ``from_zone`` check replaces the old ``_returning_from_graveyard``
        flag. Revival counters live in the engine counter system (readable via
        ``.counters``), not a card-private attribute.
        """
        if event.from_zone == Zone.STACK:
            event.counters['revival'] = event.counters.get('revival', 0) + 8

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone
        from engine.game import remove_counter
        source = self

        def _dies_condition(game: Any, event: dict) -> bool:
            creature = event.creature
            if creature is not source:
                return False
            return source.counters.get('revival', 0) > 0

        def _dies_effect(game: GameState) -> None:
            owner = getattr(source, 'owner', None)
            if owner is None:
                return
            source.controller = owner
            graveyard = owner.zones[Zone.GRAVEYARD]
            if graveyard.contains(source):
                remove_counter(game, source, 'revival', 1)
                move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_dies_condition, effect=_dies_effect, source=self, controller=controller))
