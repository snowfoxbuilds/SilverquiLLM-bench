"""Card implementation for Thunderdrum Soloist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ThunderdrumSoloist(Creature):
    """Thunderdrum Soloist — {1}{R} — Creature — Dwarf Bard — 1/3.

    Reach
    Opus — Whenever you cast an instant or sorcery spell, this creature deals
    1 damage to each opponent. If five or more mana was spent to cast that
    spell, this creature deals 3 damage to each opponent instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thunderdrum Soloist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.OPUS)
        kwargs.setdefault("subtypes", {"Dwarf", "Bard"})
        kwargs.setdefault(
            "rules_text",
            "Reach\nOpus — Whenever you cast an instant or sorcery spell, "
            "this creature deals 1 damage to each opponent. If five or more "
            "mana was spent to cast that spell, this creature deals 3 damage "
            "to each opponent instead.",
        )
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", mana_spent: int = 0) -> None:
        """Opus trigger: deal damage to each opponent."""
        damage = 3 if mana_spent >= 5 else 1
        controller = self.controller
        for player in game.players:
            if player is not controller:
                player.life -= damage

