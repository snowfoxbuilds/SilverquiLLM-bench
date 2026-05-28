"""Card implementation for Fiery Annihilation."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class FieryAnnihilation(Instant):
    """Fiery Annihilation — {2}{R} — Instant.

    Fiery Annihilation deals 5 damage to target creature. Exile up to one
    target Equipment attached to that creature. If that creature would die
    this turn, exile it instead.

    FDN collector number 86.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Fiery Annihilation')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}'))
        kwargs.setdefault('rules_text', 'Fiery Annihilation deals 5 damage to target creature. Exile up to one target Equipment attached to that creature. If that creature would die this turn, exile it instead.')
        super().__init__(**kwargs)

    def get_targets(self, game: 'GameState') -> list:
        """Target creature (required) and up to one target Equipment attached to it."""
        return [TargetRequirement(filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()), description='target creature', zone=Zone.BATTLEFIELD), TargetRequirement(filter_fn=lambda obj: 'Equipment' in getattr(obj, 'subtypes', set()), description='up to one target Equipment attached to that creature', zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: 'GameState') -> None:
        """Deal 5 damage, exile attached equipment, set exile replacement."""
        from engine.game import deal_damage, exile
        chosen = getattr(self, 'chosen_targets', None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, 'card_types', set()):
            return
        controller = self.controller
        deal_damage(game, self, target, 5)
        equip_target = chosen[1] if len(chosen) > 1 else None
        if equip_target is not None:
            exile(game, equip_target)
        else:
            attached = getattr(target, 'attached_equipments', [])
            if not attached:
                attached = [obj for player in game.players for obj in game.get_battlefield(player).get_all() if getattr(obj, 'attached_to', None) is target and 'Equipment' in getattr(obj, 'subtypes', set())]
            if attached:
                if controller is not None:
                    try:
                        equip = controller.choose_card(attached, 'Equipment to exile')
                    except Exception:
                        equip = attached[0]
                else:
                    equip = attached[0]
                if equip is not None:
                    exile(game, equip)
        target._exile_on_death = True
        from engine.triggers import TriggerRegistration
        _target_ref = target

        def _death_condition(game: Any, event: dict) -> bool:
            return event.creature is _target_ref

        def _death_effect(game: 'GameState') -> None:
            ctrl = getattr(_target_ref, 'controller', None) or getattr(_target_ref, 'owner', None)
            if ctrl is not None:
                graveyard = ctrl.zones[Zone.GRAVEYARD]
                if graveyard.contains(_target_ref):
                    graveyard.remove(_target_ref)
                    exile(game, _target_ref)
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_death_condition, effect=_death_effect, source=self, controller=controller))
