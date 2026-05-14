"""Card implementation for Celestial Armor."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Artifact
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import Keyword, ManaCost
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _make_equip_ability(
    equipment: Artifact,
    generic_cost: int,
) -> ActivatedAbility:
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
        controller = getattr(src, "controller", None)
        if controller is None:
            return False
        if controller.mana_pool.total() < generic_cost:
            return False
        controller.mana_pool.pay(ManaCost(generic=generic_cost))
        return True

    def _effect(game: Any) -> None:
        target = getattr(source, "_current_target", None)
        if target is not None:
            source.equip(target, game)

    return ActivatedAbility(
        cost=_cost,
        effect=_effect,
        description=f"Equip {{{generic_cost}}} (sorcery speed)",
    )
def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class CelestialArmor(Artifact):
    """Celestial Armor — {2}{W} — Flash.
    When this Equipment enters, attach it to target creature you control.
    That creature gains hexproof and indestructible until end of turn.
    Equipped creature gets +2/+0 and has flying. Equip {3}{W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Celestial Armor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "When this Equipment enters, attach it to target creature you "
            "control. That creature gains hexproof and indestructible until "
            "end of turn.\n"
            "Equipped creature gets +2/+0 and has flying.\n"
            "Equip {3}{W}",
        )
        super().__init__(**kwargs)
        self.keywords = self.keywords | Keyword.FLASH
        self.attached_to: Any | None = None
        self._pt_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        # ENGINE LIMITATION: Equip cost is {3}{W} (colored mana), but the
        # engine only supports generic mana payment. We approximate as {4}.
        return [_make_equip_ability(self, generic_cost=4)]

    def equip(self, target: Any, game: Any) -> None:
        self.attached_to = target
        self._register_effect(game)

    def register_triggers(self, game: Any) -> None:
        """Register ETB trigger: auto-attach to target creature and grant
        hexproof + indestructible until end of turn."""
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _self_etb_condition(game: Any, data: dict) -> bool:
            return data.get("permanent") is source

        def _effect(game: Any) -> None:
            """Attach to a target creature and grant temporary protection."""
            controller = source.controller
            if controller is None:
                return
            # Find a target creature on the controller's battlefield
            battlefield = game.get_battlefield(controller)
            target_creature = None
            from engine.types import CardType as _CT
            for card in battlefield.get_all():
                if _CT.CREATURE in getattr(card, "card_types", set()) and card is not source:
                    target_creature = card
                    break
            if target_creature is None:
                return

            # Auto-attach
            source.equip(target_creature, game)

            # Grant hexproof and indestructible until end of turn
            # ENGINE LIMITATION: "until end of turn" effects should be
            # removed during the cleanup step. The engine does not yet
            # support DURATION_UNTIL_END_OF_TURN, so we use DURATION_PERMANENT
            # and the effect will persist longer than intended.
            protected_creature = target_creature

            def _apply_protection(game: Any) -> None:
                if not _is_on_battlefield(game, protected_creature):
                    return
                protected_creature.keywords = (
                    protected_creature.keywords | Keyword.HEXPROOF | Keyword.INDESTRUCTIBLE
                )

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_protection,
                duration=DURATION_PERMANENT,
            ))

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply_pt(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2

        def _apply_ability(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.FLYING

        if self._pt_effect_ref is None:
            pt_effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            )
            self._pt_effect_ref = game.effect_manager.add(pt_effect)

        if self._ability_effect_ref is None:
            ability_effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_ability,
                duration=DURATION_PERMANENT,
            )
            self._ability_effect_ref = game.effect_manager.add(ability_effect)
