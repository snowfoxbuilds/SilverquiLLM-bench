"""Card implementation for Celestial Armor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Artifact
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _make_equip_ability(equipment: "CelestialArmor") -> ActivatedAbility:
    """Equip {3}{W} — attach to target creature you control.

    ENGINE LIMITATION: Equip cost is {3}{W} (colored mana), but the engine
    only supports generic mana payment. We approximate as generic {4}.
    """
    source = equipment

    def _cost(game: Any, src: Any) -> bool:
        controller = getattr(src, "controller", None)
        if controller is None:
            return False
        # ENGINE LIMITATION: colored equip cost {3}{W} approximated as {4}.
        if controller.mana_pool.total() < 4:
            return False
        controller.mana_pool.pay(ManaCost(generic=4))
        return True

    def _effect(game: Any) -> None:
        target = getattr(source, "_current_target", None)
        if target is not None:
            source.equip(target, game)

    return ActivatedAbility(
        cost=_cost,
        effect=_effect,
        description="Equip {3}{W} (sorcery speed)",
    )


class CelestialArmor(Artifact):
    """Celestial Armor — {2}{W} — Equipment — Flash.

    When this Equipment enters, attach it to target creature you control.
    That creature gains hexproof and indestructible until end of turn.
    Equipped creature gets +2/+0 and has flying.
    Equip {3}{W}.
    """

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

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the Equip {3}{W} ability."""
        return [_make_equip_ability(self)]

    # ------------------------------------------------------------------
    # Equip helper
    # ------------------------------------------------------------------

    def equip(self, target: Any, game: Any) -> None:
        """Attach this equipment to *target* creature and register effects."""
        self.attached_to = target
        self._register_equip_effects(game)

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return targeting requirement: target creature you control."""
        controller = self.controller or getattr(self, "owner", None)

        def _filter(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            # Must be controlled by this spell's controller
            return getattr(obj, "controller", None) is controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    # ------------------------------------------------------------------
    # ETB — per KEY_DECISIONS, self-ETB effects go in on_resolve()
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """ETB: attach to target creature you control, grant hexproof and
        indestructible until end of turn."""
        controller = self.controller
        if controller is None:
            return

        # Determine target — use chosen_targets (from StackObject.targets)
        target_creature = None
        chosen = getattr(self, "chosen_targets", None)
        if chosen:
            target_creature = chosen[0]

        if target_creature is None:
            return

        # Validate target is still a legal creature we control
        if not _is_on_battlefield(game, target_creature):
            return
        if CardType.CREATURE not in getattr(target_creature, "card_types", set()):
            return
        # Controller check — if creature changed controllers, fizzle
        if getattr(target_creature, "controller", None) is not controller:
            return

        # Auto-attach
        self.equip(target_creature, game)

        # Grant hexproof and indestructible until end of turn
        protected_creature = target_creature

        def _apply_protection(game: Any) -> None:
            if not _is_on_battlefield(game, protected_creature):
                return
            protected_creature.keywords = (
                protected_creature.keywords | Keyword.HEXPROOF | Keyword.INDESTRUCTIBLE
            )

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_protection,
            duration=DURATION_END_OF_TURN,
        ))

    # ------------------------------------------------------------------
    # Continuous effects for equipped creature (+2/+0 and flying)
    # ------------------------------------------------------------------

    def _register_equip_effects(self, game: Any) -> None:
        """Register permanent continuous effects for +2/+0 (Layer 7c) and
        flying (Layer 6) on the equipped creature."""
        equip_ref = self

        def _apply_pt(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2

        def _apply_flying(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.FLYING

        if self._pt_effect_ref is None:
            self._pt_effect_ref = game.effect_manager.add(ContinuousEffect(
                source=equip_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            ))

        if self._ability_effect_ref is None:
            self._ability_effect_ref = game.effect_manager.add(ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_flying,
                duration=DURATION_PERMANENT,
            ))
