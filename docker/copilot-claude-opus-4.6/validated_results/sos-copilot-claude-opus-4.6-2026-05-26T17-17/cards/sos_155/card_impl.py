"""Card implementation for Noxious Newt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class NoxiousNewt(Creature):
    """Noxious Newt — {1}{G} — Creature — Salamander (1/2).

    Deathtouch
    {T}: Add {G}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Noxious Newt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("subtypes", {"Salamander"})
        super().__init__(**kwargs)
        self.has_summoning_sickness: bool = False

    def can_activate_mana_ability(self, game: "GameState") -> bool:
        """Can activate if untapped and no summoning sickness."""
        if self.is_tapped:
            return False
        if self.has_summoning_sickness:
            return False
        return True

    def activate_mana_ability(self, game: "GameState") -> None:
        """{T}: Add {G}."""
        if not self.can_activate_mana_ability(game):
            return
        self.is_tapped = True
        controller = self.controller
        controller.mana_pool.add(ManaType.GREEN, 1)
