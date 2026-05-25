"""Card implementation for Authority of the Consuls."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class AuthorityOfTheConsuls(Enchantment):
    """Authority of the Consuls — {W} — Creatures opponents control enter tapped.

    Whenever a creature an opponent controls enters, you gain 1 life.

    FDN collector number 137.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Authority of the Consuls')
        kwargs.setdefault('mana_cost', ManaCost.parse('{W}'))
        kwargs.setdefault('rules_text', 'Creatures your opponents control enter tapped.\nWhenever a creature an opponent controls enters, you gain 1 life.')
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for player in game.players:
                if player is controller:
                    continue
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, 'card_types', set()):
                        if getattr(obj, 'summoning_sick', False):
                            obj.is_tapped = True
        effect = ContinuousEffect(source=enchantment_ref, layer=Layer.ABILITY, sublayer=None, apply=_apply, duration=DURATION_PERMANENT)
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            perm_controller = getattr(permanent, 'controller', None)
            if perm_controller is controller:
                return False
            return CardType.CREATURE in getattr(permanent, 'card_types', set())

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            if hasattr(controller, 'life'):
                controller.life += 1
                game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=controller, amount=1))
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)
