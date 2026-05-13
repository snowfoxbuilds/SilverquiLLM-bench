"""Card implementation for Goldvein Pick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Artifact, ContinuousEffect
from engine.continuous_effects import Layer, SubLayer
from engine.game import create_token, sacrifice
from engine.triggers import EventType, TriggerRegistration
from engine.types import ManaCost, ManaType




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

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
class GoldveinPick(Artifact):
    """Goldvein Pick — {2} — Equipped creature gets +1/+1.
    Whenever equipped creature deals combat damage to a player, create a
    Treasure token. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goldvein Pick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Equipped creature gets +1/+1.\n"
            "Whenever equipped creature deals combat damage to a player, "
            "create a Treasure token.\nEquip {1}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [_make_equip_ability(self, generic_cost=1)]

    def equip(self, target: Any, game: Any) -> None:
        self.attached_to = target
        self._register_effect(game)

    def register_triggers(self, game: Any) -> None:
        """Register combat damage trigger for Treasure token creation."""
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            """Check if the equipped creature dealt combat damage to a player."""
            creature = source.attached_to
            if creature is None:
                return False
            damage_source = data.get("source")
            target = data.get("target")
            # The equipped creature must be the damage source and the target
            # must be a player (has 'life' attribute).
            return (
                damage_source is creature
                and hasattr(target, "life")
                and data.get("is_combat", False)
            )

        def _effect(game: Any) -> None:
            """Create a Treasure token for the controller."""
            from engine.card import Artifact as _Artifact
            from engine.game import create_token
            from engine.types import ManaType

            controller = source.controller
            if controller is None:
                return

            treasure = _Artifact(name="Treasure", mana_cost=ManaCost({}))
            treasure.subtypes = {"Treasure"}
            treasure.is_token = True
            # ENGINE LIMITATION: Treasure tokens should have a mana ability
            # "{T}, Sacrifice this: Add one mana of any color." The engine
            # does not yet support sacrifice-as-cost for mana abilities.
            create_token(game, controller, treasure)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.DEALS_DAMAGE,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 1
            creature.base_toughness += 1

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)
