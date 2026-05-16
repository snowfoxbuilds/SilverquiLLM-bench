"""Card implementation for Valkyrie's Call."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, Enchantment
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.types import CardType, Keyword, ManaCost
from engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class ValkyrieSCall(Enchantment):
    """Valkyrie's Call — {3}{W}{W} — Enchantment.

    Whenever a nontoken, non-Angel creature you control dies, return that
    card to the battlefield under its owner's control with a +1/+1 counter
    on it. It has flying and is an Angel in addition to its other types.

    FDN collector number 27.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', "Valkyrie's Call")
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{W}{W}'))
        kwargs.setdefault('rules_text', "Whenever a nontoken, non-Angel creature you control dies, return that card to the battlefield under its owner's control with a +1/+1 counter on it. It has flying and is an Angel in addition to its other types.")
        super().__init__(**kwargs)
        self._angel_effects: list[ContinuousEffect] = []

    def register_triggers(self, game: 'GameState') -> None:
        """Register death trigger: return nontoken non-Angel creature."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._valkyrie_dying_queue: list[Any] = []

        def _dies_condition(game: Any, event: dict) -> bool:
            creature = event.creature
            if creature is None:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(creature, 'controller', None) is not ctrl:
                return False
            if getattr(creature, 'is_token', False):
                return False
            if 'Angel' in getattr(creature, 'subtypes', set()):
                return False
            source._valkyrie_dying_queue.append(creature)
            return True

        def _dies_effect(game: 'GameState') -> None:
            if not source._valkyrie_dying_queue:
                return
            creature = source._valkyrie_dying_queue.pop(0)
            if creature is None:
                return
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            owner = getattr(creature, 'owner', ctrl)
            from engine.types import Zone
            graveyard = owner.zones[Zone.GRAVEYARD]
            if not graveyard.contains(creature):
                return
            creature.controller = owner
            move_to_zone(game, creature, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            add_counter(game, creature, '+1/+1', 1)
            if hasattr(creature, '_original_plus_one_counters'):
                creature._original_plus_one_counters = creature.plus_one_counters
            creature_ref = creature

            def _apply_angel(game: Any) -> None:
                if not _is_on_battlefield(game, creature_ref):
                    return
                creature_ref.keywords = creature_ref.keywords | Keyword.FLYING
                creature_ref.subtypes = creature_ref.subtypes | {'Angel'}
            effect = game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.ABILITY, sublayer=None, apply=_apply_angel, duration=DURATION_PERMANENT))
            source._angel_effects.append(effect)
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_dies_condition, effect=_dies_effect, source=self, controller=controller))
