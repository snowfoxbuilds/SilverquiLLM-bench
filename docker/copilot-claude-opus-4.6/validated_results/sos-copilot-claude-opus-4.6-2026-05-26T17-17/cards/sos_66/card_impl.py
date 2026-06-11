"""Card implementation for Run Behind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RunBehind(Instant):
    """Run Behind — {3}{U} — Instant.

    This spell costs {1} less to cast if it targets an attacking creature.
    Target creature's owner puts it on their choice of the top or bottom
    of their library.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Run Behind")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game: "GameState") -> int:
        """Costs {1} less if targeting an attacking creature."""
        targets = getattr(self, "chosen_targets", None)
        if targets and len(targets) > 0:
            target = targets[0]
            if getattr(target, "is_attacking", False):
                return 1
        return 0

    def get_total_cost(self, game: "GameState") -> ManaCost:
        """Return the total cost after reductions."""
        reduction = self.cost_reduction(game)
        new_generic = max(0, self.mana_cost.generic - reduction)
        return ManaCost(generic=new_generic, pips=dict(self.mana_cost.pips))

    def on_resolve(self, game: "GameState") -> None:
        """Put target creature on top or bottom of owner's library."""
        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return
        target = targets[0]
        owner = target.owner
        if owner is None:
            return

        # Remove from battlefield
        bf = game.get_battlefield(target.controller or owner)
        if bf.contains(target):
            bf.remove(target)

        # Put on top of owner's library (default choice)
        library = game.get_library(owner)
        library.add(target)
