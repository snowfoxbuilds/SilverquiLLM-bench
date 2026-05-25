"""Card implementation for Beast-Kin Ranger."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class BeastKinRanger(Creature):
    """Beast-Kin Ranger — {2}{G} — 3/3 — Elf Ranger — Trample.

    Whenever another creature you control enters, this creature gets
    +1/+0 until end of turn.

    FDN collector number 100.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Beast-Kin Ranger')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('subtypes', {'Elf', 'Ranger'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Trample\nWhenever another creature you control enters, this creature gets +1/+0 until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            perm_ctrl = getattr(permanent, 'controller', None)
            if perm_ctrl is not ctrl:
                return False
            card_types = getattr(permanent, 'card_types', set())
            return CardType.CREATURE in card_types

        def _effect(game: 'GameState') -> None:
            if not _is_on_battlefield(game, source):
                return
            creature_ref = source

            def _apply(game: Any) -> None:
                if _is_on_battlefield(game, creature_ref):
                    creature_ref.modified_power += 1
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
