"""Card implementation for Burst Lightning."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Instant, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    # Real pipeline: targets stored by cast_spell on the card
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    # Test backdoor: attribute set directly by test code
    return getattr(card, "_resolve_target", None)

class BurstLightning(Instant):
    """Burst Lightning — {R} — Deal 2 damage to any target (base mode).

    Kicker {4} is not implemented; always deals 2 damage.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burst Lightning")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {4}\n"
            "Burst Lightning deals 2 damage to any target. "
            "If this spell was kicked, it deals 4 damage instead.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Any target: any creature on the battlefield or any player."""
        targets: list[Any] = []
        for player in game.players:
            targets.append(player)
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()) or hasattr(obj, "life"),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Deal 2 damage to the chosen target (base, unkicked)."""
        from benchmarks.sos.workspace.engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is not None:
            deal_damage(game, self, target, 2)
