"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Creature — Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def grant_casualty(self, game: "GameState", spell: Any) -> bool:
        """Check if casualty 1 can be paid for the given spell."""
        controller = self.controller
        if controller is None:
            return False
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if obj is self:
                continue
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                if getattr(obj, "power", 0) >= 1:
                    return True
        return False

    def register_triggers(self, game: "GameState") -> None:
        """Register casualty trigger for instants/sorceries."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Grant casualty 1 to instants/sorceries cast by controller."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        spell.casualty = 1
