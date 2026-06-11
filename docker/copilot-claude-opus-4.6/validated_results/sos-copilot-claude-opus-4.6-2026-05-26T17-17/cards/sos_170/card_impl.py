"""Card implementation for Abigale, Poet Laureate // Heroic Stanza."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class AbigalePoetLaureateHeroicStanza(Creature):
    """Abigale, Poet Laureate // Heroic Stanza — {1}{W}{B} // {1}{W/B}.

    Legendary Creature — Bird Bard — 2/3. Flying.
    Whenever you cast a creature spell, Abigale becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abigale, Poet Laureate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("subtypes", {"Bird", "Bard"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.is_legendary: bool = True
        self.spell_name: str = "Heroic Stanza"
        self.spell_mana_cost: ManaCost = ManaCost.parse("{1}{W/B}")

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Abigale does NOT enter prepared."""
        self.prepared = False

    def on_creature_cast(self, game: "GameState", creature: Any) -> None:
        """Whenever you cast a creature spell, Abigale becomes prepared."""
        self.prepared = True

    def on_spell_cast(self, game: "GameState", spell: Any) -> None:
        """Non-creature spells do not trigger the ability."""
        # Only creature spells trigger — this is handled by on_creature_cast
        pass

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.prepared is True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Heroic Stanza, unpreparing Abigale."""
        if not self.prepared:
            return
        self.prepared = False
