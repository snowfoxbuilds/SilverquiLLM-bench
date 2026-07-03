"""Card implementation for Maelstrom Artisan // Rocket Volley."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RocketVolley(Sorcery):
    """Prepared spell copy for Maelstrom Artisan."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rocket Volley")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)


class MaelstromArtisanRocketVolley(Creature):
    """Maelstrom Artisan."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Maelstrom Artisan")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{R}"))
        kwargs.setdefault("subtypes", {"Minotaur", "Sorcerer"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return RocketVolley(owner=self.owner, controller=self.controller)
