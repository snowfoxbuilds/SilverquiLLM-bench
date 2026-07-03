"""Card implementation for Grave Researcher // Reanimate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _ReanimateSpell:
    """The spell side (Reanimate) of the double-faced card."""

    def __init__(self) -> None:
        self.name = "Reanimate"
        self.mana_cost = ManaCost.parse("{B}")


class GraveResearcher(Creature):
    """Grave Researcher // Reanimate — {2}{B} — Creature — Troll Warlock.

    3/3. At the beginning of your upkeep, surveil 1. Then if there are three
    or more creature cards in your graveyard, this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grave Researcher")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", {"Troll", "Warlock"})
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.spell_name: str = "Reanimate"

    def on_upkeep(self, game: "GameState") -> None:
        """At beginning of upkeep: surveil 1, then check graveyard for prepared."""
        owner = self.controller or self.owner
        library = game.get_library(owner)
        gy = game.get_graveyard(owner)

        # Surveil 1: look at top card, put it in graveyard (default behavior)
        top_cards = library.top(1)
        if top_cards:
            card = top_cards[0]
            library.remove(card)
            gy.add(card)

        # Check if 3+ creature cards in graveyard
        creature_count = sum(
            1 for c in gy.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )
        self.prepared = creature_count >= 3

    def get_spell_side(self) -> Any:
        """Return the spell side (Reanimate) if prepared."""
        if self.prepared:
            return _ReanimateSpell()
        return None
