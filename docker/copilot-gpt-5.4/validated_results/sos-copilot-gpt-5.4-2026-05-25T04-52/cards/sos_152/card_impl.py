"""Card implementation for Infirmary Healer // Stream of Life."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class StreamOfLife(Sorcery):
    """Prepared spell copy for Infirmary Healer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stream of Life")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        super().__init__(**kwargs)


class InfirmaryHealerStreamOfLife(Creature):
    """Infirmary Healer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Infirmary Healer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return StreamOfLife(owner=self.owner, controller=self.controller)
