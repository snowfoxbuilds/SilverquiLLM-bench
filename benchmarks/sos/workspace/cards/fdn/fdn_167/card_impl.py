"""Card implementation for Tolarian Terror."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TolarianTerror(Creature):
    """Tolarian Terror — {6}{U} — 5/5 — Serpent — Ward {2}.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.

    FDN collector number 167.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tolarian Terror")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{U}"))
        kwargs.setdefault("subtypes", {"Serpent"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nWard {2}",
        )
        super().__init__(**kwargs)
        self.ward_cost = ManaCost(generic=2)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by {1} for each instant/sorcery in graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count
