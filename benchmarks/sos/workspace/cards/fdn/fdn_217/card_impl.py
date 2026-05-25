"""Card implementation for Dwynen, Gilt-Leaf Daen."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class DwynenGiltLeafDaen(Creature):
    """Dwynen, Gilt-Leaf Daen — {2}{G}{G} — 3/4 — Legendary Elf Warrior.

    Reach
    Other Elf creatures you control get +1/+1.
    Whenever Dwynen attacks, you gain 1 life for each attacking Elf
    you control.

    FDN collector number 217.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Dwynen, Gilt-Leaf Daen')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}{G}'))
        kwargs.setdefault('subtypes', {'Elf', 'Warrior'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('keywords', Keyword.REACH)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Reach\nOther Elf creatures you control get +1/+1.\nWhenever Dwynen attacks, you gain 1 life for each attacking Elf you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register lord effect and attack trigger."""
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _apply_lord(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None or not _is_on_battlefield(game, source):
                return
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                if obj is source:
                    continue
                if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                    continue
                if 'Elf' not in getattr(obj, 'subtypes', set()):
                    continue
                obj.modified_power += 1
                obj.modified_toughness += 1
        game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_lord, duration=DURATION_PERMANENT))

        def _attack_condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _attack_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            elf_count = 0
            for obj in bf.get_all():
                if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                    continue
                if 'Elf' not in getattr(obj, 'subtypes', set()):
                    continue
                if getattr(obj, 'is_attacking', False):
                    elf_count += 1
            if elf_count > 0:
                ctrl.life += elf_count
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))
