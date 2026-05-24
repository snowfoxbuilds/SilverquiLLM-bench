"""Card implementation for Leyline Axe."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

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

class LeylineAxe(Artifact):
    """Leyline Axe — {4} — Equipped creature gets +1/+1 and has double strike
    and trample. Equip {3}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Leyline Axe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "If this card is in your opening hand, you may begin the game "
            "with it on the battlefield.\n"
            "Equipped creature gets +1/+1 and has double strike and trample.\n"
            "Equip {3}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._pt_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [_make_equip_ability(self, generic_cost=3)]

    def equip(self, target: Any, game: Any) -> None:
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply_pt(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.modified_power += 1
            creature.modified_toughness += 1

        def _apply_ability(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE

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
