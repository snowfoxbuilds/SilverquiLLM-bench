"""Card implementation for Diary of Dreams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Artifact, ActivatedAbility
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DiaryOfDreams(Artifact):
    """Diary of Dreams — {2} — Artifact — Book.

    Whenever you cast an instant or sorcery spell, put a page counter on this artifact.
    {5}, {T}: Draw a card. This ability costs {1} less to activate for each page counter.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Diary of Dreams")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", {"Book"})
        super().__init__(**kwargs)
        self.page_counters: int = 0

    def on_spell_cast(self, game: "GameState", spell_type: str = "") -> None:
        """Trigger: add page counter when controller casts instant/sorcery."""
        if spell_type in ("instant", "sorcery"):
            self.page_counters += 1

    def get_activation_cost(self, game: "GameState") -> int:
        """Return effective mana cost for the draw ability."""
        cost = max(0, 5 - self.page_counters)
        return cost

    def can_activate(self, game: "GameState") -> bool:
        """Check if the draw ability can be activated (must not be tapped)."""
        return not self.tapped

    def activate(self, game: "GameState") -> None:
        """Activate: tap and draw a card."""
        self.tapped = True
        controller = self.controller or self.owner
        from engine.game import draw_card
        draw_card(game, controller)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the activated ability for this artifact."""
        def _cost(game: "GameState") -> bool:
            return self.can_activate(game)

        def _effect(game: "GameState") -> None:
            self.activate(game)

        ability = ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{5}, {T}: Draw a card. Costs {1} less per page counter.",
        )
        ability.base_cost = 5  # type: ignore[attr-defined]
        ability.mana_cost = ManaCost.parse("{5}")  # type: ignore[attr-defined]
        return [ability]
