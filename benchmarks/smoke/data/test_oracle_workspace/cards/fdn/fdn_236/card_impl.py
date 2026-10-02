"""Card implementation for Wildwood Scourge."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import CounterAddedTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class WildwoodScourge(Creature):
    """Wildwood Scourge — {X}{G} — 0/0 — Hydra.

    This creature enters with X +1/+1 counters on it.
    Whenever one or more +1/+1 counters are put on another non-Hydra
    creature you control, put a +1/+1 counter on this creature.

    FDN collector number 236.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Wildwood Scourge')
        kwargs.setdefault('mana_cost', ManaCost.parse('{X}{G}'))
        kwargs.setdefault('subtypes', {'Hydra'})
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 0)
        kwargs.setdefault('rules_text', 'This creature enters with X +1/+1 counters on it.\nWhenever one or more +1/+1 counters are put on another non-Hydra creature you control, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)
        self.x_value: int = 0

    def enters_battlefield_with(self, game: 'GameState', event: Any) -> None:
        """Enter with X +1/+1 counters (rule 614.1c replacement).

        ``x_value`` is the value chosen for {X} when the spell was cast; the
        replay executor derives it from the observed cast funding before
        resolution. When no X evidence is available it stays 0 and the creature
        honestly enters at 0/0 and dies to SBAs — no counter is fabricated.
        """
        if self.x_value > 0:
            event.counters['+1/+1'] = event.counters.get('+1/+1', 0) + self.x_value

    def register_triggers(self, game: 'GameState') -> None:
        """Register the +1/+1 counter synergy trigger.

        Whenever one or more +1/+1 counters are put on another non-Hydra
        creature you control, put a +1/+1 counter on this creature. A creature
        that *enters* with +1/+1 counters counts as having counters put on it
        (rule 614.1c), so the enters-with-counters primitive fires
        ``CounterAddedTriggeredEvent`` for it and this synergy sees it.
        """
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._counter_synergy = True

        def _condition(game: Any, event: dict) -> bool:
            # Read only fields the declared CounterAddedTriggeredEvent carries
            # (permanent / counter_type / amount) — there is no ``target``.
            target = event.permanent
            if target is None or target is source:
                return False
            if CardType.CREATURE not in getattr(target, 'card_types', set()):
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(target, 'controller', None) is not ctrl:
                return False
            if 'Hydra' in getattr(target, 'subtypes', set()):
                return False
            counter_type = event.counter_type
            if counter_type != '+1/+1':
                return False
            return True

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=CounterAddedTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
