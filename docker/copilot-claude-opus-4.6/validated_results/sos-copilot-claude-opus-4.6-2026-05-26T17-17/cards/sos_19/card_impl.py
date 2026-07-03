"""Card implementation for Honorbound Page // Forum's Favor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class HonorboundPageForumsFavor(Creature):
    """Honorbound Page // Forum's Favor.

    Front face: {3}{W} Creature — Cat Cleric 3/3
    First strike. This creature enters prepared.

    Back face: Forum's Favor — {W} Sorcery
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Honorbound Page")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "First strike\nThis creature enters prepared.",
        )
        super().__init__(**kwargs)
        self.prepared: bool = True
        self.spell_name: str = "Forum's Favor"

    def on_resolve(self, game: "GameState") -> None:
        """When this resolves (enters battlefield), it enters prepared."""
        self.prepared = True

    def cast_prepared_spell(self, game: "GameState", player: "Player") -> None:
        """Cast a copy of Forum's Favor, unpreparing this creature."""
        from engine.stack import StackObject

        if not self.prepared:
            raise Exception("Cannot cast spell — creature is not prepared")

        # Unprepare the creature
        self.prepared = False

        # Create a spell copy of Forum's Favor on the stack
        # Forum's Favor is a {W} Sorcery — for now just resolve as a no-op
        # (the spec doesn't detail what Forum's Favor does beyond the prepared mechanic)
        def _on_resolve(g: "GameState") -> None:
            pass  # Forum's Favor effect placeholder

        stack_obj = StackObject(
            source=self,
            controller=player,
            on_resolve=_on_resolve,
        )
        game.stack.push(stack_obj)

