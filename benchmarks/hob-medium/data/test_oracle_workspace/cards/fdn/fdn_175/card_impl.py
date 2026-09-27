"""Card implementation for Hero's Downfall."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first.
    """
    # Real pipeline: targets stored by cast_spell on the card
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    # Test backdoor: attribute set directly by test code
    return None

class HerosDownfall(Instant):
    """Hero's Downfall — {1}{B}{B} — Destroy target creature or planeswalker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hero's Downfall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("rules_text", "Destroy target creature or planeswalker.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature or planeswalker on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: bool(getattr(obj, "card_types", set()) & {CardType.CREATURE, CardType.PLANESWALKER}),
                description="target creature or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature or planeswalker."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature or planeswalker on the battlefield.
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                    destroy(game, target)
                    return
