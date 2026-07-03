"""Card implementation for Molten Note."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage, untap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MoltenNote(Sorcery):
    """Molten Note."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Molten Note")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Molten Note deals damage equal to the amount of mana spent to cast it to target creature. "
            "Untap all creatures you control. Flashback {6}{R}{W}.",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{6}{R}{W}")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if isinstance(target, Creature):
            deal_damage(game, self, target, int(getattr(self, "mana_spent", 0)))
        if controller is None:
            return
        for permanent in game.get_battlefield(controller).get_all():
            if isinstance(permanent, Creature):
                untap(game, permanent)
