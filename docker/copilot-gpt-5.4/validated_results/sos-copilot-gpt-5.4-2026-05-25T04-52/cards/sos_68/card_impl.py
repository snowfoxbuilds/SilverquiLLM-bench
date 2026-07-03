"""Card implementation for Spellbook Seeker // Careful Study."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class CarefulStudy(Sorcery):
    """Prepared spell copy for Spellbook Seeker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Careful Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class SpellbookSeekerCarefulStudy(Creature):
    """Spellbook Seeker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spellbook Seeker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Bird", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nThis creature enters prepared.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return CarefulStudy(owner=self.owner, controller=self.controller)
