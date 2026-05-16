"""Card implementation for Embercleave."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Artifact, Creature, Enchantment, Instant, ManaAbility, Sorcery
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, DURATION_PERMANENT, Layer, SubLayer
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class Embercleave(Artifact):
    """Embercleave — {4}{R}{R} — Legendary Artifact — Equipment

    Flash
    This spell costs {1} less to cast for each attacking creature you
    control.
    When Embercleave enters the battlefield, attach it to target creature
    you control.
    Equipped creature gets +1/+1 and has double strike and trample.
    Equip {3}

    SPG collector number 77.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Embercleave')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{R}{R}'))
        kwargs.setdefault('subtypes', set())
        kwargs['subtypes'] = (kwargs.get('subtypes') or set()) | {'Equipment'}
        kwargs.setdefault('supertypes', set())
        kwargs['supertypes'] = (kwargs.get('supertypes') or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault('keywords', Keyword.FLASH)
        kwargs.setdefault('rules_text', 'Flash\nThis spell costs {1} less to cast for each attacking creature you control.\nWhen Embercleave enters the battlefield, attach it to target creature you control.\nEquipped creature gets +1/+1 and has double strike and trample.\nEquip {3}')
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def cost_reduction(self, game: Any) -> int:
        """Cost {1} less for each attacking creature you control."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        count = 0
        bf = game.get_battlefield(controller)
        for perm in bf.get_all():
            if CardType.CREATURE in getattr(perm, 'card_types', set()) and getattr(perm, 'is_attacking', False):
                count += 1
        return count

    def equip(self, target: Any, game: Any) -> None:
        """Attach Embercleave to *target* creature."""
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply_keywords(g: Any) -> None:
            if not _is_on_battlefield(g, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(g, creature):
                return
            creature.keywords = creature.keywords | Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE

        def _apply_pt(g: Any) -> None:
            if not _is_on_battlefield(g, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(g, creature):
                return
            creature.base_power += 1
            creature.base_toughness += 1
        if self._effect_ref is None:
            effect_kw = ContinuousEffect(source=equip_ref, layer=Layer.ABILITY, sublayer=None, apply=_apply_keywords, duration=DURATION_PERMANENT)
            game.effect_manager.add(effect_kw)
            effect_pt = ContinuousEffect(source=equip_ref, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply_pt, duration=DURATION_PERMANENT)
            self._effect_ref = game.effect_manager.add(effect_pt)

    def _do_etb_attach(self, game: Any) -> None:
        """Perform the ETB attach — find a creature you control and equip it."""
        controller = self.controller or self.owner
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        creatures = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set())]
        if creatures:
            target = creatures[0]
            self.equip(target, game)

    def on_resolve(self, game: Any) -> None:
        """When Embercleave resolves, it enters the battlefield and attaches."""
        self._do_etb_attach(game)

    def register_triggers(self, game: Any) -> None:
        from engine.triggers import TriggerRegistration
        source = self

        def _etb_condition(g: Any, event: dict) -> bool:
            return event.permanent is source

        def _etb_effect(g: Any) -> None:
            source._do_etb_attach(g)
        reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_etb_condition, effect=_etb_effect, source=self, controller=source.controller or source.owner)
        game.trigger_manager.register(reg)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, 'controller', None)
            if controller is None:
                return False
            cost = ManaCost(generic=3)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            target = getattr(source, '_current_target', None)
            if target is not None:
                source.equip(target, game)
        return [ActivatedAbility(cost=_cost, effect=_effect, description='Equip {3} (sorcery speed)')]
