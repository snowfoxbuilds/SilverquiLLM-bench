"""Card implementation for Run Away Together."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState




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
class RunAwayTogether(Instant):
    """Run Away Together — {1}{U} — Choose two target creatures controlled
    by different players. Return those creatures to their owners' hands.

    FDN collector number 162.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Run Away Together")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two target creatures controlled by different players. "
            "Return those creatures to their owners' hands.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creatures controlled by different players."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        # Each requirement accepts any creature; the "different controllers"
        # constraint is validated at target-selection time (not per-filter).
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature (first — must differ in controller from second)",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature (second — must differ in controller from first)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Return both target creatures to their owners' hands."""
        from engine.zones import move_to_zone

        target1 = _get_chosen_target_idx(self, game, 0)
        target2 = _get_chosen_target_idx(self, game, 1)

        # Fizzle if targets don't have different controllers
        if target1 is not None and target2 is not None:
            ctrl1 = getattr(target1, "controller", None)
            ctrl2 = getattr(target2, "controller", None)
            if ctrl1 is ctrl2:
                return  # illegal — must be different controllers

        for target in [target1, target2]:
            if target is None:
                continue
            for player in game.players:
                if game.get_battlefield(player).contains(target):
                    move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
                    break
