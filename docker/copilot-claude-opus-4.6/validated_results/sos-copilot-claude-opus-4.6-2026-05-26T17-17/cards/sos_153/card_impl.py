"""Card implementation for Lumaret's Favor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


@dataclass
class CastTriggerResult:
    """Result of an on_cast_trigger indicating whether to copy the spell."""
    copy_spell: bool = False


class LumaretsFavor(Instant):
    """Lumaret's Favor — {1}{G} — Instant.

    Infusion — When you cast this spell, copy it if you gained life this turn.
    Target creature gets +2/+4 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lumaret's Favor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Requires one target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Target creature gets +2/+4 until end of turn."""
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        target = targets[0]
        target.modified_power += 2
        target.modified_toughness += 4

    def on_cast_trigger(self, game: "GameState") -> CastTriggerResult | None:
        """Infusion: copy if controller gained life this turn."""
        controller = self.controller
        life_gained = getattr(controller, "life_gained_this_turn", 0)
        if life_gained > 0:
            return CastTriggerResult(copy_spell=True)
        return None
