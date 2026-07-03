"""Card implementation for Melancholic Poet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MelancholicPoet(Creature):
    """{1}{B} Creature — Elf Bard 2/2.

    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, each opponent loses 1 life and you gain 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Melancholic Poet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Elf", "Bard"})
        super().__init__(**kwargs)

    def on_trigger_spell_cast(self, game: "GameState", spell: Any) -> None:
        """Repartee trigger."""
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        targets = getattr(spell, "chosen_targets", None)
        if not targets:
            return
        if not any(CardType.CREATURE in getattr(t, "card_types", set()) for t in targets):
            return
        for player in game.players:
            if player is not self.controller:
                player.life -= 1
        self.controller.life += 1
