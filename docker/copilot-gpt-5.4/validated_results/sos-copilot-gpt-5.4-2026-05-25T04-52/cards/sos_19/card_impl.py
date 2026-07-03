"""Card implementation for Honorbound Page // Forum's Favor."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

class ForumsFavor(Sorcery):
    """Prepared spell copy for Honorbound Page."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Forum's Favor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class HonorboundPageForumsFavor(Creature):
    """Honorbound Page."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Honorbound Page")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "First strike\nThis creature enters prepared. (While it's prepared, you may cast "
            "a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return ForumsFavor(owner=self.owner, controller=self.controller)
