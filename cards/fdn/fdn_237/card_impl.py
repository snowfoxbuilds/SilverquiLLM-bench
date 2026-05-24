"""Card implementation for Balmor, Battlemage Captain."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class BalmorBattlemageCaptain(Creature):
    """Balmor, Battlemage Captain — {U}{R} — 1/3 — Legendary Bird Wizard.

    Flying
    Whenever you cast an instant or sorcery spell, creatures you control
    get +1/+0 and gain trample until end of turn.

    FDN collector number 237.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Balmor, Battlemage Captain')
        kwargs.setdefault('mana_cost', ManaCost.parse('{U}{R}'))
        kwargs.setdefault('subtypes', {'Bird', 'Wizard'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Flying\nWhenever you cast an instant or sorcery spell, creatures you control get +1/+0 and gain trample until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register spell-cast prowess-like trigger."""
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            caster = event.player or event.controller
            if caster is not ctrl:
                return False
            spell = event.card or event.spell
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return

            def _apply_pt(game: Any) -> None:
                bf = game.get_battlefield(ctrl)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, 'card_types', set()):
                        obj.modified_power += 1

            def _apply_trample(game: Any) -> None:
                bf = game.get_battlefield(ctrl)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, 'card_types', set()):
                        obj.keywords = obj.keywords | Keyword.TRAMPLE
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_pt, duration=DURATION_END_OF_TURN))
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.ABILITY, sublayer=None, apply=_apply_trample, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
