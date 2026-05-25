"""Card implementation for Stab."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Stab(Instant):
    """Stab — {B} — Instant.

    Target creature gets -2/-2 until end of turn.

    FDN collector number 71.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stab")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets -2/-2 until end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Requires one target creature."""
        from benchmarks.sos.workspace.engine.types import Zone
        return [TargetRequirement(
            filter_fn=lambda obj, g=game: CardType.CREATURE in getattr(obj, "card_types", set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """Give target creature -2/-2 until end of turn."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen or chosen[0] is None:
            return
        target = chosen[0]

        # Verify still valid: must be on battlefield AND still a creature
        from benchmarks.sos.workspace.engine.types import Zone
        found = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                found = True
                break
        if not found:
            return
        # Single-target-fizzle: revalidate creature type
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        def _apply(game: Any) -> None:
            target.modified_power = target.modified_power - 2
            target.modified_toughness = target.modified_toughness - 2

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_END_OF_TURN,
        ))
