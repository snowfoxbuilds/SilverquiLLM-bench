"""Card implementation for Prismari, the Inspiration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class PrismariTheInspiration(Creature):
    """Prismari, the Inspiration — {5}{U}{R} — Legendary Creature — Elder Dragon.

    7/7, Flying, Ward—Pay 5 life.
    Instant and sorcery spells you cast have storm.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prismari, the Inspiration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{U}{R}"))
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.WARD)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        super().__init__(**kwargs)
        self.ward_cost = 5

    @property
    def is_legendary(self) -> bool:
        return True

    def grants_storm_to(self, spell: Any) -> bool:
        """Check if this dragon grants storm to the given spell."""
        from engine.card import Instant, Sorcery
        if not isinstance(spell, (Instant, Sorcery)):
            return False
        spell_controller = getattr(spell, "controller", None) or getattr(spell, "owner", None)
        my_controller = self.controller or self.owner
        return spell_controller is my_controller

    def get_storm_copies(self, game: "GameState", spell: Any) -> list[Any]:
        """Return storm copies based on spells cast this turn."""
        storm_count = getattr(game, "storm_count", 0)
        copies = []
        for _ in range(storm_count):
            import copy
            copy_spell = copy.copy(spell)
            copy_spell.chosen_targets = list(getattr(spell, "chosen_targets", []) or [])
            copies.append(copy_spell)
        return copies
