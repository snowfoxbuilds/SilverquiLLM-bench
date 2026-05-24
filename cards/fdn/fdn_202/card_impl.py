"""Card implementation for Hidetsugu's Second Rite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HidetsugusSecondRite(Instant):
    """Hidetsugu's Second Rite — {3}{R} — Instant.

    If target player has exactly 10 life, Hidetsugu's Second Rite deals
    10 damage to that player.

    FDN collector number 202.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hidetsugu's Second Rite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault(
            "rules_text",
            "If target player has exactly 10 life, Hidetsugu's Second Rite "
            "deals 10 damage to that player.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Target player."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Deal 10 damage if target has exactly 10 life."""
        from benchmarks.sos.workspace.engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if getattr(target, "life", 0) == 10:
            deal_damage(game, self, target, 10)
