"""Card implementation for Abrade."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature, Instant, Mode, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)
def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class Abrade(Instant):
    """Abrade — {1}{R} — Choose one.

    - Abrade deals 3 damage to target creature.
    - Destroy target artifact.

    FDN collector number 188.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abrade")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Abrade deals 3 damage to target creature.\n"
            "• Destroy target artifact.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Abrade deals 3 damage to target creature."),
            Mode(name="Destroy Artifact", description="Destroy target artifact."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            from benchmarks.sos.workspace.engine.game import deal_damage
            target = _get_target(self)
            if target is not None:
                deal_damage(game, self, target, 3)
        elif mode == 1:
            from benchmarks.sos.workspace.engine.game import destroy
            target = _get_target(self)
            if target is not None and _is_on_battlefield(game, target):
                destroy(game, target)
