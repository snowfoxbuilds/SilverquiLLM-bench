"""Card implementation for Luminous Rebuke."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

class LuminousRebuke(Instant):
    """Luminous Rebuke — {4}{W} — Destroy target creature.

    This spell costs {3} less to cast if it targets a tapped creature.
    (Cost reduction not implemented.)

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

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    destroy(game, target)
                    return
