"""Card implementation for Giada, Font of Hope."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class GiadaFontOfHope(Creature):
    """Giada, Font of Hope — {1}{W} — 2/2 — Legendary Angel.

    Flying, vigilance
    Each other Angel you control enters with an additional +1/+1 counter
    on it for each Angel you already control.
    {T}: Add {W}. Spend this mana only to cast an Angel spell.

    FDN collector number 141.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Giada, Font of Hope')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Angel'})
        kwargs.setdefault('keywords', Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flying, vigilance\nEach other Angel you control enters with an additional +1/+1 counter on it for each Angel you already control.\n{T}: Add {W}. Spend this mana only to cast an Angel spell.')
        super().__init__(**kwargs)
        self.is_legendary = True

    def register_triggers(self, game: 'GameState') -> None:
        """Register ETB trigger for other Angels entering."""
        from collections import deque
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        _angel_queue: deque = deque()

        def _cond_with_capture(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(permanent, 'controller', None) is not ctrl:
                return False
            if 'Angel' not in getattr(permanent, 'subtypes', set()):
                return False
            _angel_queue.append(permanent)
            return True

        def _final_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            if not _angel_queue:
                return
            target = _angel_queue.popleft()
            bf = game.get_battlefield(ctrl)
            angel_count = 0
            for obj in bf.get_all():
                if 'Angel' in getattr(obj, 'subtypes', set()) and obj is not target:
                    angel_count += 1
            if angel_count > 0:
                add_counter(game, target, '+1/+1', angel_count)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_cond_with_capture, effect=_final_effect, source=self, controller=controller))

    def get_mana_abilities(self) -> list:
        """Return the tap-for-white mana ability."""
        from engine.card import ManaAbility
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            src.is_tapped = True
            return True

        def _mana_produced(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            from engine.types import ManaType
            ctrl.mana_pool.add(ManaType.WHITE, 1)
        return [ManaAbility(cost=_cost, mana_produced=_mana_produced, description='{T}: Add {W}. Spend this mana only to cast an Angel spell.')]
