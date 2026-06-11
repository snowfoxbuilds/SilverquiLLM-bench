"""Card implementation for Emeritus of Conflict // Lightning Bolt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfConflict(Creature):
    """Emeritus of Conflict // Lightning Bolt — {1}{R} — Creature — Human Wizard.

    First strike
    Whenever you cast your third spell each turn, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)

    Back face: Lightning Bolt — {R} — Instant — deals 3 damage to any target.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Conflict")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "First strike\nWhenever you cast your third spell each turn, "
            "this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False
        self.back_face_name: str = "Lightning Bolt"
        self.back_face_mana_cost: ManaCost = ManaCost.parse("{R}")

    def on_spell_cast(self, game: "GameState", caster: Any, spell_number: int = 0) -> None:
        """Trigger: becomes prepared when the controller casts their third spell."""
        if caster is self.controller and spell_number >= 3:
            self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the back face spell (Lightning Bolt copy). Unprepares the creature."""
        self.is_prepared = False
