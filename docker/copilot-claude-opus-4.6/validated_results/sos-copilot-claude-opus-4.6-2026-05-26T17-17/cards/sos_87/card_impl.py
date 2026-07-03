"""Card implementation for Lecturing Scornmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LecturingScornmage(Creature):
    """{B} Creature — Human Warlock 1/1.

    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, put a +1/+1 counter on this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lecturing Scornmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        super().__init__(**kwargs)

    def on_trigger_spell_cast(self, game: "GameState", spell: Any) -> None:
        """Repartee trigger."""
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        targets = getattr(spell, "chosen_targets", None)
        if not targets:
            return
        for t in targets:
            if CardType.CREATURE in getattr(t, "card_types", set()):
                self.plus_one_counters += 1
                self._base_plus_one_counters = self.plus_one_counters
                return
