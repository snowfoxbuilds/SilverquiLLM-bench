"""Card implementation for Campus Composer // Aqueous Aria."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AqueousAria(Sorcery):
    """Prepared spell copy for Campus Composer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aqueous Aria")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)


class CampusComposerAqueousAria(Creature):
    """Campus Composer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Campus Composer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Bard"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Ward {2}\nThis creature enters prepared. (While it's prepared, you may cast a copy "
            "of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{2}")

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return AqueousAria(owner=self.owner, controller=self.controller)
