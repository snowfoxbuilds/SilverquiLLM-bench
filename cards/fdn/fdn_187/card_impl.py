"""Card implementation for Zombify."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Instant, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

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

class Zombify(Sorcery):
    """Zombify — {3}{B} — Return target creature card from your graveyard
    to the battlefield.

    FDN collector number 187.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zombify")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return target creature card from your graveyard to the "
            "battlefield.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature card in your graveyard."""
        controller = self.controller
        targets: list[Any] = []
        if controller is not None:
            for obj in controller.zones[Zone.GRAVEYARD].get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "owner", None) is _c
                ),
                description="target creature card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ] if targets else []

    def on_resolve(self, game: GameState) -> None:
        """Return the target creature card from graveyard to battlefield."""
        from benchmarks.sos.workspace.engine.zones import move_to_zone

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still in a graveyard
        for player in game.players:
            gy = player.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
                    return
