"""Card implementation for Ashroot Animist."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.card_queries import choose_object
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Zone
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class AshrootAnimist(Creature):
    """Ashroot Animist — {2}{R}{G} — 4/4 — Lizard Druid.

    Trample
    Whenever this creature attacks, another target creature you control
    gains trample and gets +X/+X until end of turn, where X is this
    creature's power.

    FDN collector number 117.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Ashroot Animist')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}{G}'))
        kwargs.setdefault('subtypes', {'Lizard', 'Druid'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', "Trample\nWhenever this creature attacks, another target creature you control gains trample and gets +X/+X until end of turn, where X is this creature's power.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for trample + power buff."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and c is not source]
            if not candidates:
                return
            chosen = choose_object(game, ctrl, candidates, 'creature to get +X/+X and trample', source_card=source)
            if chosen is None:
                return
            power_val = getattr(source, 'power', getattr(source, 'base_power', 4))

            def _apply(game: Any) -> None:
                chosen.modified_power += power_val
                chosen.modified_toughness += power_val
                chosen.keywords = (getattr(chosen, 'keywords', None) or Keyword(0)) | Keyword.TRAMPLE
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
