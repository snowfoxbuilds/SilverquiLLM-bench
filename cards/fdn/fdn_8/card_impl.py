"""Card implementation for Dauntless Veteran."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class DauntlessVeteran(Creature):
    """Dauntless Veteran — {1}{W}{W} — 2/2 — Human Soldier.

    Whenever this creature attacks, creatures you control get +1/+1 until
    end of turn.

    FDN collector number 8.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Dauntless Veteran')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}{W}'))
        kwargs.setdefault('subtypes', {'Human', 'Soldier'})
        kwargs.setdefault('keywords', Keyword(0))
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Whenever this creature attacks, creatures you control get +1/+1 until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger: creatures you control get +1/+1 until EOT."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            """Fire when this creature attacks."""
            return event.creature is source

        def _attack_effect(game: 'GameState') -> None:
            """Creatures you control get +1/+1 until end of turn."""
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return

            def _apply_buff(game: Any) -> None:
                c = getattr(source, 'controller', None)
                if c is None:
                    return
                battlefield = game.get_battlefield(c)
                for obj in battlefield.get_all():
                    if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                        continue
                    obj.base_power += 1
                    obj.base_toughness += 1
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_buff, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))
