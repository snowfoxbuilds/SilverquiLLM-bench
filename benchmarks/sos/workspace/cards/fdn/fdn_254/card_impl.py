"""Card implementation for Heraldic Banner."""

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

class HeraldicBanner(Artifact):
    """Heraldic Banner — {3} — As enters, choose a color. Creatures of that
    color get +1/+0. {T}: Add one mana of the chosen color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heraldic Banner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, choose a color.\n"
            "Creatures you control of the chosen color get +1/+0.\n"
            "{T}: Add one mana of the chosen color.",
        )
        super().__init__(**kwargs)
        self.chosen_color: str | None = None

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                # Simplified: add colorless (color choice not modelled)
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add one mana of the chosen color."),
        ]
