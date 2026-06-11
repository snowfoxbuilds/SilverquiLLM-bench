"""Card implementation for Quill-Blade Laureate // Twofold Intent."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class TwofoldIntent(Sorcery):
    """Prepared spell copy for Quill-Blade Laureate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Twofold Intent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)


class QuillBladeLaureateTwofoldIntent(Creature):
    """Quill-Blade Laureate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quill-Blade Laureate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("keywords", Keyword.DOUBLE_STRIKE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Double strike\nThis creature enters prepared. (While it's prepared, you may cast "
            "a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return TwofoldIntent(owner=self.owner, controller=self.controller)
