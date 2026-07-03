"""Card implementation for Lluwen, Exchange Student // Pest Friend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LluwenExchangeStudentPestFriend(Creature):
    """Lluwen, Exchange Student // Pest Friend — {2}{B}{G} — 3/4 Legendary Creature — Elf Druid.

    Lluwen enters prepared.
    Exile a creature card from your graveyard: Lluwen becomes prepared. Activate only as a sorcery.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lluwen, Exchange Student")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.is_legendary: bool = True
        self.is_prepared: bool = False
        self.activation_timing: str = "sorcery"

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Lluwen enters the battlefield prepared."""
        self.is_prepared = True

    def can_activate_ability(self, game: "GameState") -> bool:
        """Check if there's a creature card in the graveyard to exile."""
        controller = self.controller
        graveyard = game.get_graveyard(controller)
        for obj in graveyard.get_all():
            card_types = getattr(obj, "card_types", set())
            if CardType.CREATURE in card_types:
                return True
        return False

    def activate_ability(self, game: "GameState", target: Any = None) -> None:
        """Exile a creature card from graveyard to become prepared."""
        if target is None:
            return
        controller = self.controller
        graveyard = game.get_graveyard(controller)
        if target in graveyard:
            graveyard.remove(target)
            game.get_exile(controller).add(target)
            self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Pest Friend and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
