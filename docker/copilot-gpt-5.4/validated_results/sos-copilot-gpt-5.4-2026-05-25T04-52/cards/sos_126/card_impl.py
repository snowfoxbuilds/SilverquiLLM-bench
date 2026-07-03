"""Card implementation for Pigment Wrangler // Striking Palette."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class StrikingPalette(Sorcery):
    """Prepared spell copy for Pigment Wrangler."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Striking Palette")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class PigmentWranglerStrikingPalette(Creature):
    """Pigment Wrangler."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pigment Wrangler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return StrikingPalette(owner=self.owner, controller=self.controller)
