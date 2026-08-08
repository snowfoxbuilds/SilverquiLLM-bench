"""Card implementation for Luminous Rebuke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Return the first chosen target (from cast_spell) or the test backdoor."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class LuminousRebuke(Instant):
    """Luminous Rebuke — {4}{W} — Instant.

    This spell costs {3} less to cast if it targets a tapped creature.
    Destroy target creature.

    FDN collector number 20.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Luminous Rebuke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {3} less to cast if it targets a tapped "
            "creature.\nDestroy target creature.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game: "GameState", targets: list[Any] | None = None) -> int:
        """Costs {3} less if it targets a tapped creature."""
        for target in targets or ():
            if (
                target is not None
                and CardType.CREATURE in getattr(target, "card_types", set())
                and getattr(target, "is_tapped", False)
            ):
                return 3
        return 0

    def on_resolve(self, game: "GameState") -> None:
        """Destroy the target creature."""
        from engine.game import destroy

        target = _get_chosen_target(self)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    destroy(game, target)
                    return
