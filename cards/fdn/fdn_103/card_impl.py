"""Card implementation for Elfsworn Giant."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ElfswornGiant(Creature):
    """Elfsworn Giant — {3}{G}{G} — 5/3 — Giant — Reach.

    Landfall — Whenever a land you control enters, create a 1/1 green
    Elf Warrior creature token.

    FDN collector number 103.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Elfsworn Giant')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}{G}'))
        kwargs.setdefault('subtypes', {'Giant'})
        kwargs.setdefault('keywords', Keyword.REACH)
        kwargs.setdefault('base_power', 5)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Reach\nLandfall — Whenever a land you control enters, create a 1/1 green Elf Warrior creature token.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import create_token
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
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Elf Warrior', subtypes={'Elf', 'Warrior'}, base_power=1, base_toughness=1, rules_text='')
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_landfall_condition, effect=_landfall_effect, source=self, controller=controller))
