"""Card implementation for Orysa, Tide Choreographer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class OrysaTideChoreographer(Creature):
    """Orysa, Tide Choreographer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Orysa, Tide Choreographer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Merfolk", "Bard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {3} less to cast if creatures you control have total toughness "
            "10 or greater.\nWhen Orysa enters, draw two cards.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: GameState) -> int:
        controller = self.controller
        if controller is None:
            return 0
        total_toughness = sum(
            permanent.toughness
            for permanent in game.get_battlefield(controller).get_all()
            if isinstance(permanent, Creature)
        )
        return 3 if total_toughness >= 10 else 0

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        draw_card(game, controller)
        draw_card(game, controller)
