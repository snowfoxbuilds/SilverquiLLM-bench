"""Card implementation for Mocking Sprite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class MockingSprite(Creature):
    """Mocking Sprite — {2}{U} — 2/1 — Faerie Rogue — Flying.

    Instant and sorcery spells you cast cost {1} less to cast.

    FDN collector number 159.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mocking Sprite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Faerie", "Rogue"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nInstant and sorcery spells you cast cost {1} less to cast.",
        )
        super().__init__(**kwargs)

    def spell_cost_reduction(
        self, game: "GameState", spell: Any, caster: "Player"
    ) -> int:
        """Instant/sorcery spells the controller casts cost {1} less."""
        if self.controller is not caster:
            return 0
        types = getattr(spell, "card_types", set())
        if CardType.INSTANT in types or CardType.SORCERY in types:
            return 1
        return 0
