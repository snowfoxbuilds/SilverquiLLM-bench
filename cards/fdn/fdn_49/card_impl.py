"""Card implementation for Rune-Sealed Wall."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from cards.registry import CardRegistry

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True

class RuneSealedWall(ArtifactCreature):
    """Rune-Sealed Wall — {2}{U} — 0/6 — Wall

    Defender
    {T}: Surveil 1.

    FDN collector number 49.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rune-Sealed Wall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Wall"})
        kwargs.setdefault("keywords", Keyword.DEFENDER)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "Defender\n{T}: Surveil 1.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            if len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                # Surveil: may put into graveyard (simplified: always
                # put into graveyard for deterministic behaviour).
                graveyard = controller.zones[Zone.GRAVEYARD]
                graveyard.add(card)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Surveil 1.",
        )]
