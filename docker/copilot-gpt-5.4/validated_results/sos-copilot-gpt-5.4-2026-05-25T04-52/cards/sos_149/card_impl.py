"""Card implementation for Germination Practicum."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GerminationPracticum(Sorcery):
    """Germination Practicum."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Germination Practicum")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self.paradigm_enabled = True

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        for permanent in game.get_battlefield(controller).get_all():
            if isinstance(permanent, Creature):
                add_counter(game, permanent, "+1/+1", 2)
