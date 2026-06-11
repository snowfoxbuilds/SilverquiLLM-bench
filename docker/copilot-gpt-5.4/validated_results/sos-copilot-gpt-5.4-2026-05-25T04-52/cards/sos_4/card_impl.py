"""Card implementation for Together as One."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage, draw_card
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TogetherAsOne(Sorcery):
    """Together as One."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player draws X cards, Together as One deals X damage to any "
            "target, and you gain X life, where X is the number of colors of mana spent to "
            "cast this spell.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        colors_spent = len(set(getattr(self, "colors_spent", [])))
        if colors_spent <= 0:
            return

        targets = getattr(self, "chosen_targets", [])
        if len(targets) < 2 or self.controller is None:
            return

        player_target = targets[0]
        damage_target = targets[1]

        for _ in range(colors_spent):
            draw_card(game, player_target)
        deal_damage(game, self, damage_target, colors_spent)
        self.controller.life += colors_spent
