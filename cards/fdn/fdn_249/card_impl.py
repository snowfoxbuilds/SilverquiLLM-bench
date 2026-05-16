"""Card implementation for Adventuring Gear."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Artifact
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from engine.types import Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _make_equip_ability(equipment: Artifact, generic_cost: int) -> ActivatedAbility:
    """Return an :class:`ActivatedAbility` representing *Equip {N}*.

    The ability pays *generic_cost* generic mana from the controller's mana
    pool, then calls ``equipment.equip(target, game)`` to attach the
    equipment to a target creature.  Equip is sorcery-speed only (the engine
    should enforce timing; we document the restriction in the description).

    The target creature is read from ``equipment._current_target`` which the
    game engine is expected to set before calling the ability's effect.
    """
    source = equipment

    def _cost(game: Any, src: Any) -> bool:
        controller = getattr(src, 'controller', None)
        if controller is None:
            return False
        if controller.mana_pool.total() < generic_cost:
            return False
        controller.mana_pool.pay(ManaCost(generic=generic_cost))
        return True

    def _effect(game: Any) -> None:
        target = getattr(source, '_current_target', None)
        if target is not None:
            source.equip(target, game)
    return ActivatedAbility(cost=_cost, effect=_effect, description=f'Equip {{{generic_cost}}} (sorcery speed)')

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class AdventuringGear(Artifact):
    """Adventuring Gear — {1} — Landfall — Whenever a land you control enters,
    equipped creature gets +2/+2 until end of turn. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Adventuring Gear')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}'))
        kwargs.setdefault('subtypes', set())
        kwargs['subtypes'] = (kwargs.get('subtypes') or set()) | {'Equipment'}
        kwargs.setdefault('rules_text', 'Landfall — Whenever a land you control enters, equipped creature gets +2/+2 until end of turn.\nEquip {1}')
        super().__init__(**kwargs)
        self.attached_to: Any | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [_make_equip_ability(self, generic_cost=1)]

    def equip(self, target: Any, game: Any) -> None:
        """Attach this equipment to *target* creature."""
        self.attached_to = target

    def register_triggers(self, game: Any) -> None:
        """Register landfall trigger: whenever a land you control enters,
        equipped creature gets +2/+2 until end of turn."""
        from engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            """Check if a land entered under this equipment's controller."""
            permanent = event.permanent
            if permanent is None:
                return False
            from engine.types import CardType as _CT
            if _CT.LAND not in getattr(permanent, 'card_types', set()):
                return False
            controller = getattr(source, 'controller', None)
            perm_controller = event.controller or getattr(permanent, 'controller', None)
            return controller is not None and perm_controller is controller

        def _effect(game: Any) -> None:
            """Give equipped creature +2/+2 until end of turn."""
            creature = source.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            equip_ref = source

            def _apply_landfall_pt(game: Any) -> None:
                if not _is_on_battlefield(game, equip_ref):
                    return
                c = equip_ref.attached_to
                if c is not creature:
                    return
                if c is None or not _is_on_battlefield(game, c):
                    return
                c.base_power += 2
                c.base_toughness += 2
            game.effect_manager.add(ContinuousEffect(source=equip_ref, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_landfall_pt, duration=DURATION_PERMANENT))
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
