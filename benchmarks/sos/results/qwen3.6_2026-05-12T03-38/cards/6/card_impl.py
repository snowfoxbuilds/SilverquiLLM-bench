from __future__ import annotations

from typing import Any

from engine.card import *
from engine.types import *


class AjanisResponse(Instant):
    """Ajani's Response."""

    def __init__(self, **kwargs):
        super().__init__(
            name="Ajani's Response",
            mana_cost=ManaCost.parse("{4}{W}"),
            card_types={CardType.INSTANT},
            rules_text="""This spell costs {3} less to cast if it targets a tapped creature.
Destroy target creature.""",
            **kwargs,
        )

    def cost_reduction(self, game: GameState) -> int:
        """This spell costs {3} less to cast if it targets a tapped creature."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return 0
        for target in chosen:
            if CardType.CREATURE in getattr(target, "card_types", set()):
                if getattr(target, "is_tapped", False):
                    return 3
        return 0

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature."""
        from engine.game import destroy

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    destroy(game, target)
                    return
