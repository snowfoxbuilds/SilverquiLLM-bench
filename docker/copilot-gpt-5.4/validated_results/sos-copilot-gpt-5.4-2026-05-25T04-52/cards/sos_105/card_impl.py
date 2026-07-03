"""Card implementation for Withering Curse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class WitheringCurse(Sorcery):
    """Withering Curse."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Withering Curse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "All creatures get -2/-2 until end of turn.\n"
            "Infusion — If you gained life this turn, destroy all creatures instead.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        creatures = [
            permanent
            for player in game.players
            for permanent in game.get_battlefield(player).get_all()
            if isinstance(permanent, Creature)
        ]
        if controller is not None and getattr(controller, "life_gained_this_turn", 0) > 0:
            for creature in creatures:
                destroy(game, creature)
            return

        def _apply(g: GameState) -> None:
            for player in g.players:
                for permanent in g.get_battlefield(player).get_all():
                    if isinstance(permanent, Creature):
                        permanent.modified_power -= 2
                        permanent.modified_toughness -= 2

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
