"""Card implementation for Banner of Kinship."""

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

    from benchmarks.sos.workspace.cards.registry import CardRegistry

class BannerOfKinship(Artifact):
    """Banner of Kinship — {5} — As enters, choose a creature type.
    Enters with fellowship counters. Chosen type gets +1/+1 per counter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banner of Kinship")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, choose a creature type. This artifact enters "
            "with a fellowship counter on it for each creature you control of the "
            "chosen type.\nCreatures you control of the chosen type get +1/+1 for "
            "each fellowship counter on this artifact.",
        )
        super().__init__(**kwargs)
        self.chosen_type: str | None = None
        self.fellowship_counters: int = 0
