"""Card implementation for Spectacular Skywhale."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SpectacularSkywhale(Creature):
    """Spectacular Skywhale — {2}{U}{R} — 1/4 — Creature — Elemental Whale.

    Flying
    Opus — Whenever you cast an instant or sorcery spell, this creature gets
    +3/+0 until end of turn. If five or more mana was spent to cast that spell,
    put three +1/+1 counters on this creature instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spectacular Skywhale")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{R}"))
        kwargs.setdefault("subtypes", {"Elemental", "Whale"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0

    def register_triggers(self, game: "GameState") -> None:
        """Register opus trigger — handled via on_spell_cast."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Opus: +3/+0 on instant/sorcery cast by controller.
        If 5+ mana spent, put three +1/+1 counters instead."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        # Determine mana spent
        mana_cost = getattr(spell, "mana_cost", None)
        mana_spent = 0
        if mana_cost is not None:
            mana_spent = mana_cost.cmc

        if mana_spent >= 5:
            # Put three +1/+1 counters instead
            self.plus_one_counters += 3
            self._base_plus_one_counters = self.plus_one_counters
        else:
            # +3/+0 until end of turn
            self._temp_power_bonus += 3
