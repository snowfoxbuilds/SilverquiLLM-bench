"""Card implementation for Skycoach Conductor // All Aboard."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class AllAboard(Instant):
    """Prepared spell copy for Skycoach Conductor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "All Aboard")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class SkycoachConductorAllAboard(Creature):
    """Skycoach Conductor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skycoach Conductor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Bird", "Pilot"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying, vigilance\nThis creature enters prepared.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Instant:
        return AllAboard(owner=self.owner, controller=self.controller)
