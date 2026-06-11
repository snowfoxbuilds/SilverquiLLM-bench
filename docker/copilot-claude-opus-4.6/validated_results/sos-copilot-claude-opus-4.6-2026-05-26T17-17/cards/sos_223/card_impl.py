"""Card implementation for Sanar, Unfinished Genius // Wild Idea."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Artifact
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SanarUnfinishedGeniusWildIdea(Creature):
    """Sanar, Unfinished Genius // Wild Idea — {U}{R} // {3}{U}{R}.

    Front face: Legendary Creature — Goblin Sorcerer, 0/4.
    Enters prepared.
    {T}: Create a Treasure token. Activate only if you've cast an instant or
    sorcery spell this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sanar, Unfinished Genius")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Sorcerer"})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("rules_text",
            "Sanar enters prepared.\n"
            "{T}: Create a Treasure token. Activate only if you've cast an "
            "instant or sorcery spell this turn.")
        # Set keywords to include PREPARED
        kw = kwargs.get("keywords", Keyword(0))
        # Use KeywordSet or just set the sentinel
        kwargs["keywords"] = kw
        super().__init__(**kwargs)
        # Add PREPARED keyword
        self.keywords = self.keywords | Keyword.PREPARED  # type: ignore[assignment]
        self.is_prepared: bool = False

    def enter_battlefield(self, game: "GameState") -> None:
        """Sanar enters prepared."""
        self.is_prepared = True

    def can_activate_treasure(self, game: "GameState") -> bool:
        """Return True if an instant or sorcery was cast this turn by controller."""
        controller = self.controller
        if controller is None:
            return False
        if self.is_tapped:
            return False
        spells = getattr(game, "spells_cast_this_turn", [])
        for spell_info in spells:
            spell_ctrl = spell_info.get("controller")
            spell_types = spell_info.get("types", set())
            if spell_ctrl == controller and ("instant" in spell_types or "sorcery" in spell_types):
                return True
        return False

    def activate_treasure(self, game: "GameState") -> None:
        """Activate: {T}: Create a Treasure token."""
        self.is_tapped = True
        controller = self.controller
        if controller is None:
            return
        # Create a Treasure token
        treasure = Artifact(
            name="Treasure",
            owner=controller,
            controller=controller,
        )
        treasure.is_token = True
        game.get_battlefield(controller).add(treasure)
