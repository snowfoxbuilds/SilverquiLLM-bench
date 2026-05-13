"""Card implementation for Pacifism."""

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


class Pacifism(Aura):
    """Pacifism — {1}{W} — Enchant creature. Can't attack or block.

    Implements the "can't attack or block" restriction as a layer 6
    continuous effect that removes attack/block ability.  On the engine
    side, creatures with this effect have ``is_attacking`` and
    ``is_blocking`` forcefully set to ``False`` and their ability to
    be declared as attacker/blocker is checked via the continuous effect.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pacifism")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\nEnchanted creature can't attack or block.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

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
        """Attach to the target creature and register continuous effect."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature on the battlefield.
        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        """Register the 'can't attack or block' continuous effect."""
        aura_ref = self

        def _apply_pacifism(game: GameState) -> None:
            # Stop applying if the aura itself has left the battlefield.
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            # Mark the creature as unable to attack or block.
            # We use a sentinel attribute that combat code can check.
            creature._cant_attack = True  # type: ignore[attr-defined]
            creature._cant_block = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_pacifism,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Re-register the continuous effect when entering via the casting pipeline."""
        if self._effect_ref is None and self.attached_to is not None:
            self._register_effect(game)


__all__ = ["Pacifism"]
