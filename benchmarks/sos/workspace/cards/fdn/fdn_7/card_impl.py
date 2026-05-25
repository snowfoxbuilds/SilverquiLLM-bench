"""Card implementation for Crystal Barricade."""

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

class CrystalBarricade(ArtifactCreature):
    """Crystal Barricade — {1}{W} — 0/4 Wall. Defender. You have hexproof.
    Prevent all noncombat damage to other creatures you control."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crystal Barricade")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Wall"}
        kwargs.setdefault("keywords", Keyword.DEFENDER)
        kwargs.setdefault(
            "rules_text",
            "Defender\nYou have hexproof.\n"
            "Prevent all noncombat damage that would be dealt to other creatures you control.",
        )
        super().__init__(**kwargs)
