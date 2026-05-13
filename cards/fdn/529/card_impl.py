"""Card implementation for UntamedHunger."""

from __future__ import annotations


from engine.card import Artifact, Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _creature_targets(game: Any) -> list[Any]:
    """Return all creatures on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class UntamedHunger(Aura):
    """Untamed Hunger — {2}{B} — Enchant creature gets +2/+1 and has menace.

    Implements:
    - Layer 7c: +2/+1 P/T modification.
    - Layer 6: grants menace keyword.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Untamed Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +2/+1 and has menace. "
            "(It can't be blocked except by two or more creatures.)",
        )
        super().__init__(**kwargs)
        self._pt_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast if no creature on the battlefield."""
        return bool(_creature_targets(game))

    def on_resolve(self, game: GameState) -> None:
        """Attach to the target creature and register continuous effects."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        self.attached_to = target
        self._register_effects(game)

    def _register_effects(self, game: GameState) -> None:
        """Register P/T and menace continuous effects."""
        aura_ref = self

        # Layer 7c: +2/+1
        def _apply_pt(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2
            creature.base_toughness += 1

        pt_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_PERMANENT,
        )
        self._pt_effect_ref = game.effect_manager.add(pt_effect)

        # Layer 6: grant menace
        def _apply_menace(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.MENACE

        ability_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_menace,
            duration=DURATION_PERMANENT,
        )
        self._ability_effect_ref = game.effect_manager.add(ability_effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Re-register effects if needed after entering via casting pipeline."""
        if self._pt_effect_ref is None and self.attached_to is not None:
            self._register_effects(game)


__all__ = ["UntamedHunger"]
