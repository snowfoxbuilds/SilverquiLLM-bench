"""Card implementation for Brush Off."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BrushOff(Instant):
    """Brush Off — {2}{U}{U} — Instant.

    This spell costs {1}{U} less to cast if it targets an instant or sorcery spell.
    Counter target spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brush Off")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{U}"))
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return 0
        target = chosen[0]
        card_types = getattr(target, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return 2  # {1}{U} less = 2 total reduction
        return 0

    def get_targets(self, game: "GameState") -> list[Any]:
        return [TargetRequirement(
            filter_fn=lambda obj: True,  # Any spell is a legal target
            description="target spell",
            zone=Zone.STACK,
        )]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        # Counter the spell — move to owner's graveyard
        owner = getattr(target, "owner", None)
        if owner is None:
            return
        game.get_graveyard(owner).add(target)
