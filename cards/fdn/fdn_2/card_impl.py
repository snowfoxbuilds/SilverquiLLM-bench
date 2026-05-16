"""Card implementation for Arahbo, the First Fang."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, Supertype
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class ArahboTheFirstFang(Creature):
    """Arahbo, the First Fang — {2}{W} — 2/2 — Legendary Cat Avatar.

    Other Cats you control get +1/+1.
    Whenever Arahbo or another nontoken Cat you control enters, create a
    1/1 white Cat creature token.

    FDN collector number 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Arahbo, the First Fang')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}'))
        kwargs.setdefault('subtypes', {'Cat', 'Avatar'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('keywords', Keyword(0))
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Other Cats you control get +1/+1.\nWhenever Arahbo or another nontoken Cat you control enters, create a 1/1 white Cat creature token.')
        super().__init__(**kwargs)
        self._lord_effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: 'GameState') -> None:
        """Handle Arahbo's own ETB — create a 1/1 Cat token.

        Per KEY_DECISIONS: ENTERS_BATTLEFIELD fires BEFORE register_triggers(),
        so the self-entry event has already happened by the time the trigger is
        registered. Self-ETB must therefore be handled here in on_resolve().
        """
        from engine.game import create_token
        controller = self.controller
        if controller is None:
            return
        token = Creature(name='Cat', subtypes={'Cat'}, base_power=1, base_toughness=1)
        create_token(game, controller, token)

    def register_triggers(self, game: 'GameState') -> None:
        """Register the lord effect and Cat-ETB token trigger."""
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        if self._lord_effect_ref is None:

            def _apply_lord(game: Any) -> None:
                ctrl = getattr(source, 'controller', None)
                if ctrl is None or not _is_on_battlefield(game, source):
                    return
                battlefield = game.get_battlefield(ctrl)
                for obj in battlefield.get_all():
                    if obj is source:
                        continue
                    if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                        continue
                    if 'Cat' not in getattr(obj, 'subtypes', set()):
                        continue
                    obj.base_power += 1
                    obj.base_toughness += 1
            self._lord_effect_ref = game.effect_manager.add(ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_lord, duration=DURATION_PERMANENT))

        def _etb_condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(permanent, 'controller', None) is not ctrl:
                return False
            if permanent is source:
                return True
            if getattr(permanent, 'is_token', False):
                return False
            if 'Cat' in getattr(permanent, 'subtypes', set()):
                return True
            return False

        def _etb_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Cat', subtypes={'Cat'}, base_power=1, base_toughness=1)
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_etb_condition, effect=_etb_effect, source=self, controller=controller))
