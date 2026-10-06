"""Card implementation for Crystal Barricade."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class CrystalBarricadeAbility1:
    text = "Defender (This creature can't attack.)"


class CrystalBarricadeAbility2:
    text = "You have hexproof. (You can't be the target of spells or abilities your opponents control.)"


class CrystalBarricadeAbility3:
    text = 'Prevent all noncombat damage that would be dealt to other creatures you control.'


# endregion Printed abilities


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
