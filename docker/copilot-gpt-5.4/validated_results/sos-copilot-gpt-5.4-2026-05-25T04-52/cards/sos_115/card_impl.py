"""Card implementation for Flashback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Flashback(Instant):
    """Flashback."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Flashback")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    isinstance(obj, (Instant, Sorcery))
                    and (
                        getattr(obj, "owner", None) is controller
                        or getattr(obj, "controller", None) is controller
                    )
                ),
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if not isinstance(target, (Instant, Sorcery)):
            return
        override = game.grant_zone_bound_attribute_override(
            target,
            zone=Zone.GRAVEYARD,
            attr_name="flashback_cost",
            value=target.mana_cost,
            source=self,
        )

        def _cleanup(_game: GameState) -> None:
            _game.expire_zone_bound_attribute_override(override)

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TEXT,
                apply=lambda _game: None,
                duration=DURATION_END_OF_TURN,
                on_expire=_cleanup,
            )
        )
