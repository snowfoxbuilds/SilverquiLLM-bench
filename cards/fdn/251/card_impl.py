"""Card implementation for Campus Guide."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import ManaCost


class CampusGuide(ArtifactCreature):
    """Campus Guide — {2} — 2/1 Golem. ETB: search for basic land on top."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Campus Guide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Golem"}
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for a basic "
            "land card, reveal it, then shuffle and put that card on top.",
        )
        super().__init__(**kwargs)
