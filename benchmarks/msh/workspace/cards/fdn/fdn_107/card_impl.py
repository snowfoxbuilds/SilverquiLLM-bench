"""Card implementation for Mossborn Hydra."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class MossbornHydra(Creature):
    """Mossborn Hydra — {2}{G} — 0/0 — Elemental Hydra — Trample.

    This creature enters with a +1/+1 counter on it.
    Landfall — Whenever a land you control enters, double the number of
    +1/+1 counters on this creature.

    FDN collector number 107.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Mossborn Hydra')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('subtypes', {'Elemental', 'Hydra'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE)
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 0)
        kwargs.setdefault('rules_text', 'Trample\nThis creature enters with a +1/+1 counter on it.\nLandfall — Whenever a land you control enters, double the number of +1/+1 counters on this creature.')
        super().__init__(**kwargs)

    def enters_battlefield_with(self, game: 'GameState', event: Any) -> None:
        """Enters with a +1/+1 counter (rule 614.1c replacement).

        Unconditional, so the primitive alone fixes it — the 0/0 never exists
        transiently. The Landfall trigger below then doubles from a nonzero base.
        """
        event.counters['+1/+1'] = event.counters.get('+1/+1', 0) + 1

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _landfall_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            permanent = event.permanent
            if permanent is None:
                return False
            card_types = getattr(permanent, 'card_types', set())
            if CardType.LAND not in card_types:
                return False
            perm_ctrl = getattr(permanent, 'controller', None)
            if perm_ctrl is None:
                bf = game.get_battlefield(ctrl)
                return bf.contains(permanent)
            return perm_ctrl is ctrl

        def _landfall_effect(game: 'GameState') -> None:
            from engine.game import add_counter
            current = getattr(source, 'plus_one_counters', 0)
            if current > 0:
                # Double the counters: add another `current` to reach 2×.
                add_counter(game, source, '+1/+1', current)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_landfall_condition, effect=_landfall_effect, source=self, controller=controller))
