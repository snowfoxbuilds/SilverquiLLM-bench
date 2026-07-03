"""Card implementation for Biblioplex Tomekeeper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class BiblioplexTomekeeper(ArtifactCreature):
    """Biblioplex Tomekeeper — {4} — 3/4 Artifact Creature — Construct.

    When this creature enters, choose up to one —
    • Target creature becomes prepared.
    • Target creature becomes unprepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Biblioplex Tomekeeper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("subtypes", {"Construct"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []
        self.chosen_mode: str | None = None

    def on_enter(self, game: "GameState") -> None:
        """ETB trigger: choose up to one — prepare or unprepare target creature."""
        if self.chosen_mode is None or not self.chosen_targets:
            return

        target = self.chosen_targets[0]

        if self.chosen_mode == "prepare":
            # Only creatures with prepare spells can become prepared
            if getattr(target, "has_prepare_spell", False):
                target.prepared = True
        elif self.chosen_mode == "unprepare":
            target.prepared = False
