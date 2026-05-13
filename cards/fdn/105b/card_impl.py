"""Card implementation for FellingBlow."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
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

def _get_chosen_target_idx(card: Any, game: Any, idx: int) -> Any:
    """Retrieve the *idx*-th chosen target for a spell (0-indexed)."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    # Fall back to list-based test backdoor
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    if idx == 0:
        return getattr(card, "_resolve_target", None)
    return None


class FellingBlow(Sorcery):
    """Felling Blow — {2}{G} — Put a +1/+1 counter on target creature
    you control. Then that creature deals damage equal to its power to
    target creature an opponent controls.

    FDN collector number 105.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felling Blow")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature you control. Then "
            "that creature deals damage equal to its power to target "
            "creature an opponent controls.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Two targets: your creature and opponent's creature."""
        controller = self.controller
        my_targets: list[Any] = []
        opp_targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj_ctrl = getattr(obj, "controller", None)
                    if obj_ctrl is controller:
                        my_targets.append(obj)
                    else:
                        opp_targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is not _c
                ),
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Put +1/+1 counter, then one-way fight."""
        from engine.game import deal_damage

        source_creature = _get_chosen_target_idx(self, game, 0)
        fight_target = _get_chosen_target_idx(self, game, 1)

        if source_creature is None or fight_target is None:
            return

        # Verify both are still on the battlefield
        source_valid = False
        target_valid = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(source_creature):
                source_valid = True
            if bf.contains(fight_target):
                target_valid = True

        if not source_valid:
            return

        # +1/+1 counter via plus_one_counters (not base_power mutation)
        if hasattr(source_creature, "plus_one_counters"):
            source_creature.plus_one_counters += 1
            source_creature._original_plus_one_counters = source_creature.plus_one_counters  # type: ignore[attr-defined]

        if target_valid:
            power = getattr(source_creature, "power", getattr(source_creature, "base_power", 0))
            if power > 0:
                deal_damage(game, source_creature, fight_target, power)


__all__ = ["FellingBlow"]
