"""Card implementation for Swiftfoot Boots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _make_equip_ability(equipment: "SwiftfootBoots") -> ActivatedAbility:
    """Equip {1} — attach to target creature you control."""
    source = equipment

    def _cost(game: Any, src: Any) -> bool:
        controller = getattr(src, "controller", None)
        if controller is None:
            return False
        if controller.mana_pool.total() < 1:
            return False
        controller.mana_pool.pay(ManaCost(generic=1))
        return True

    def _effect(game: Any) -> None:
        target = getattr(source, "_current_target", None)
        if target is not None:
            source.equip(target, game)

    return ActivatedAbility(
        cost=_cost,
        effect=_effect,
        description="Equip {1} (sorcery speed)",
    )


class SwiftfootBoots(Artifact):
    """Swiftfoot Boots — {2} — Equipment.

    Equipped creature has hexproof and haste.
    Equip {1}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftfoot Boots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature has hexproof and haste.\nEquip {1}")
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the Equip {1} ability."""
        return [_make_equip_ability(self)]

    # ------------------------------------------------------------------
    # Equip helper
    # ------------------------------------------------------------------

    def equip(self, target: Any, game: Any) -> None:
        """Attach this equipment to *target* creature and register effects."""
        self.attached_to = target
        self._register_equip_effects(game)

    # ------------------------------------------------------------------
    # Continuous effects — hexproof + haste (Layer 6)
    # ------------------------------------------------------------------

    def _register_equip_effects(self, game: Any) -> None:
        """Register a permanent ContinuousEffect granting hexproof and haste
        to the equipped creature (Layer 6 — ABILITY)."""
        equip_ref = self

        def _apply(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.HEXPROOF | Keyword.HASTE

        if self._effect_ref is None:
            self._effect_ref = game.effect_manager.add(ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            ))
