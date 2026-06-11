"""Card implementation for Mathemagics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Mathemagics(Sorcery):
    """Mathemagics."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mathemagics")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{X}{U}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj, _game=game: obj in _game.players,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if target not in game.players:
            return
        for _ in range(2 ** int(getattr(self, "x_value", 0))):
            draw_card(game, target)
