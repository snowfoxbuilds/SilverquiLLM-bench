"""Card implementation for Fishing Pole."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player

    from cards.registry import CardRegistry

class FishingPole(Artifact):
    """Fishing Pole — {1} — Equipment with bait counter mechanics."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fishing Pole")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has \"{1}, {T}, Tap Fishing Pole: Put a bait counter "
            "on Fishing Pole.\"\nWhenever equipped creature becomes untapped, remove "
            "a bait counter from this Equipment. If you do, create a 1/1 blue Fish "
            "creature token.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self.bait_counters: int = 0
