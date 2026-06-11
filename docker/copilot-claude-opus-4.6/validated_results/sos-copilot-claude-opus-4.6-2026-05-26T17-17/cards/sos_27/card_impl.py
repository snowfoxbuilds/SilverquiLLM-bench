"""Card implementation for Quill-Blade Laureate // Twofold Intent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class QuillBladeLaureateTwofoldIntent(Creature):
    """Quill-Blade Laureate // Twofold Intent — {1}{W} // {1}{W}.

    Creature — Human Cleric — 1/1
    Double strike
    This creature enters prepared. While prepared, you may cast a copy of
    its spell. Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quill-Blade Laureate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("keywords", Keyword.DOUBLE_STRIKE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Double strike\n"
            "This creature enters prepared. (While it's prepared, you may "
            "cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.spell_name: str = "Twofold Intent"

    def on_resolve(self, game: "GameState") -> None:
        """Enter the battlefield prepared."""
        self.prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Twofold Intent from this prepared creature.

        Raises Exception if not prepared.
        """
        if not self.prepared:
            raise Exception("Cannot cast prepared spell — creature is not prepared")
        self.prepared = False
