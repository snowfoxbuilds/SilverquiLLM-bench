"""Card implementation for Ruby, Daring Tracker."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, ManaAbility
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, 'is_tapped', False):
        return False
    source.is_tapped = True
    return True

class RubyDaringTracker(Creature):
    """Ruby, Daring Tracker — {R}{G} — 1/2 — Human Scout

    Haste
    Whenever Ruby attacks while you control a creature with power 4 or
    greater, Ruby gets +2/+2 until end of turn.
    {T}: Add {R} or {G}.

    FDN collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Ruby, Daring Tracker')
        kwargs.setdefault('mana_cost', ManaCost.parse('{R}{G}'))
        kwargs.setdefault('subtypes', {'Human', 'Scout'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('keywords', Keyword.HASTE)
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Haste\nWhenever Ruby attacks while you control a creature with power 4 or greater, Ruby gets +2/+2 until end of turn.\n{T}: Add {R} or {G}.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for +2/+2 buff."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if event.creature is not source:
                return False
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                    continue
                power = getattr(obj, 'power', getattr(obj, 'base_power', 0))
                if power >= 4:
                    return True
            return False

        def _effect(game: 'GameState') -> None:

            def _apply_buff(game: Any) -> None:
                source.modified_power += 2
                source.modified_toughness += 2
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_buff, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _make_effect(mtype: ManaType):

            def _effect(game: Any) -> None:
                controller = source.controller
                if controller is not None:
                    controller.mana_pool.add(mtype, 1)
            return _effect
        return [ManaAbility(cost=_tap_cost, mana_produced=_make_effect(ManaType.RED), description='{T}: Add {R}.'), ManaAbility(cost=_tap_cost, mana_produced=_make_effect(ManaType.GREEN), description='{T}: Add {G}.')]
