"""Card implementation for Pilfer."""

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

class Pilfer(Sorcery):
    """Pilfer — {1}{B} — Target opponent reveals hand; you choose a nonland card to discard."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pilfer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target opponent reveals their hand. You choose a nonland card "
            "from it. That player discards that card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target opponent."""
        controller = self.controller
        targets: list[Any] = [
            p for p in game.players if p is not controller
        ]
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: hasattr(obj, "life") and obj is not _c,
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Target opponent reveals hand; controller chooses a nonland card to discard."""
        from benchmarks.sos.workspace.engine.game import discard

        target = _get_chosen_target(self, game)
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        # Reveal hand and pick a nonland card.
        hand = game.get_hand(target)
        nonland_cards = [
            c for c in hand.get_all()
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        if not nonland_cards:
            return

        chosen = controller.choose_card(nonland_cards, "Choose a nonland card to discard")
        if chosen is not None:
            discard(game, target, chosen)
