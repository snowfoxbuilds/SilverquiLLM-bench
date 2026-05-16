"""Card implementation for Skyknight Squire."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.types import CardType, Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class SkyknightSquire(Creature):
    """Skyknight Squire — {1}{W} — 1/1 — Cat Scout.

    Whenever another creature you control enters, put a +1/+1 counter on
    this creature.
    As long as this creature has three or more +1/+1 counters on it, it
    has flying and is a Knight in addition to its other types.

    FDN collector number 23.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Skyknight Squire')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Cat', 'Scout'})
        kwargs.setdefault('keywords', Keyword(0))
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'Whenever another creature you control enters, put a +1/+1 counter on this creature.\nAs long as this creature has three or more +1/+1 counters on it, it has flying and is a Knight in addition to its other types.')
        super().__init__(**kwargs)
        self._threshold_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: 'GameState') -> None:
        """Register ETB trigger and threshold continuous effect."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _etb_condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(permanent, 'controller', None) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(permanent, 'card_types', set()):
                return False
            return True

        def _etb_effect(game: 'GameState') -> None:
            if not _is_on_battlefield(game, source):
                return
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_original_plus_one_counters'):
                source._original_plus_one_counters = source.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_etb_condition, effect=_etb_effect, source=self, controller=controller))
        if self._threshold_effect_ref is None:
            original_subtypes = frozenset(source.subtypes)

            def _apply_threshold(game: Any) -> None:
                if not _is_on_battlefield(game, source):
                    return
                source.subtypes = set(original_subtypes)
                if getattr(source, 'plus_one_counters', 0) >= 3:
                    source.keywords = source.keywords | Keyword.FLYING
                    source.subtypes = source.subtypes | {'Knight'}
            self._threshold_effect_ref = game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.ABILITY, sublayer=None, apply=_apply_threshold, duration=DURATION_PERMANENT))
