"""Card implementation for Drake Hatcher."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature
from engine.types import Keyword, ManaCost
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class DrakeHatcher(Creature):
    """Drake Hatcher — {1}{U} — 1/3 — Human Wizard.

    Vigilance, prowess
    Whenever this creature deals combat damage to a player, put that many
    incubation counters on it.
    Remove three incubation counters from this creature: Create a 2/2 blue
    Drake creature token with flying.

    FDN collector number 35.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Drake Hatcher')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}'))
        kwargs.setdefault('subtypes', {'Human', 'Wizard'})
        kwargs.setdefault('keywords', Keyword.VIGILANCE | Keyword.PROWESS)
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Vigilance, prowess\nWhenever this creature deals combat damage to a player, put that many incubation counters on it.\nRemove three incubation counters from this creature: Create a 2/2 blue Drake creature token with flying.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register combat damage trigger: add incubation counters."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        _captured: dict[str, int] = {}

        def _damage_condition(game: Any, event: dict) -> bool:
            if event.source is not source:
                return False
            if not event.is_combat:
                return False
            target = event.target
            from engine.player import Player
            if not isinstance(target, Player):
                return False
            _captured['amount'] = event.amount
            return True

        def _damage_effect(game: 'GameState') -> None:
            from engine.game import add_counter
            amount = _captured.get('amount', getattr(source, 'power', source.modified_power))
            # "incubation" counters live in the engine counter system (readable
            # via `.counters`, syncable by the replay executor's CounterAdded
            # consumption) — not a card-private attribute.
            add_counter(game, source, 'incubation', amount)
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_damage_condition, effect=_damage_effect, source=self, controller=controller))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Remove three incubation counters: Create a 2/2 blue Drake token with flying."""
        source = self

        def _cost(game: Any, src: Any) -> bool:
            from engine.game import remove_counter
            counters = src.counters.get('incubation', 0)
            if counters < 3:
                return False
            remove_counter(game, src, 'incubation', 3)
            return True

        def _effect(game: Any) -> None:
            from engine.game import create_token
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Drake', subtypes={'Drake'}, keywords=Keyword.FLYING, base_power=2, base_toughness=2)
            create_token(game, ctrl, token)
        return [ActivatedAbility(cost=_cost, effect=_effect, description='Remove three incubation counters from this creature: Create a 2/2 blue Drake creature token with flying.')]
