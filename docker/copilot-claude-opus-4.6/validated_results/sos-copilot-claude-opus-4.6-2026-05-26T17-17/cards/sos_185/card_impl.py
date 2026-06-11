"""Card implementation for Elemental Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ElementalMascot(Creature):
    """Elemental Mascot — {1}{U}{R} — 1/4 Creature — Elemental Bird.

    Flying, vigilance
    Opus — Whenever you cast an instant or sorcery spell, this creature gets
    +1/+0 until end of turn. If five or more mana was spent to cast that spell,
    exile the top card of your library. You may play that card until the end of
    your next turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elemental Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{R}"))
        kwargs.setdefault("subtypes", {"Elemental", "Bird"})
        kwargs.setdefault(
            "keywords",
            Keyword.FLYING | Keyword.VIGILANCE,
        )
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0

    @property
    def power(self) -> int:
        """Current power including temp bonus from opus."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters + self._temp_power_bonus

    def register_triggers(self, game: "GameState") -> None:
        """Register opus trigger — handled via on_spell_cast."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Opus: +1/+0 on instant/sorcery cast. If 5+ mana, exile top of library."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        # Only triggers on instants/sorceries
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Only triggers on controller's spells
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        # +1/+0 until end of turn
        self._temp_power_bonus += 1

        # Determine mana spent
        mana_spent = getattr(event, "mana_spent", 0)
        if mana_spent == 0:
            mana_cost = getattr(spell, "mana_cost", None)
            if mana_cost is not None:
                mana_spent = mana_cost.cmc

        # If 5+ mana, exile top card of library
        if mana_spent >= 5:
            controller = self.controller
            library = controller.zones[Zone.LIBRARY]
            lib_cards = library.get_all()
            if lib_cards:
                # Top of library is last element
                top_card = lib_cards[-1]
                library.remove(top_card)
                exile_zone = controller.zones[Zone.EXILE]
                exile_zone.add(top_card)
