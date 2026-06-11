"""Card implementation for Vastlands Scavenger // Bind to Life."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class BindToLife(Instant):
    """Prepared spell copy for Vastlands Scavenger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bind to Life")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class VastlandsScavengerBindToLife(Creature):
    """Vastlands Scavenger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vastlands Scavenger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{G}"))
        kwargs.setdefault("subtypes", {"Bear", "Druid"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Deathtouch\nThis creature enters prepared. (While it's prepared, you may cast "
            "a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Instant:
        return BindToLife(owner=self.owner, controller=self.controller)
