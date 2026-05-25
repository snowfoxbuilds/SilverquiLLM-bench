"""Card implementation for Frenzied Goblin."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer
from engine.types import CardType, ManaCost
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class FrenziedGoblin(Creature):
    """Frenzied Goblin — {R} — 1/1 — Goblin Berserker.

    Whenever this creature attacks, you may pay {R}. If you do, target
    creature can't block this turn.

    FDN collector number 199.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Frenzied Goblin')
        kwargs.setdefault('mana_cost', ManaCost.parse('{R}'))
        kwargs.setdefault('subtypes', {'Goblin', 'Berserker'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', "Whenever this creature attacks, you may pay {R}. If you do, target creature can't block this turn.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for can't-block."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            try:
                if not ctrl.choose_yes_no('Pay {R} to make a creature unable to block?'):
                    return
            except Exception:
                return
            try:
                ctrl.mana_pool.pay(ManaCost.parse('{R}'))
            except Exception:
                return
            all_creatures: list = []
            for player in game.players:
                for perm in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(perm, 'card_types', set()):
                        all_creatures.append(perm)
            if not all_creatures:
                return
            try:
                target = ctrl.choose_card(all_creatures, "Choose a creature that can't block this turn")
            except Exception:
                target = all_creatures[0]
            if target is not None:
                target._cant_block = True

                def _apply(game: Any) -> None:
                    target._cant_block = True
                game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.ABILITY, sublayer=None, apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
