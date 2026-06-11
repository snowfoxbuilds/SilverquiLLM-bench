"""Card implementation for Teacher's Pest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TeachersPest(Creature):
    """Teacher's Pest — {B}{G} — Creature — Skeleton Pest, 1/1.

    Menace
    Whenever this creature attacks, you gain 1 life.
    {B}{G}: Return this card from your graveyard to the battlefield tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Teacher's Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{G}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Pest"})
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Menace\nWhenever this creature attacks, you gain 1 life.\n"
            "{B}{G}: Return this card from your graveyard to the battlefield tapped.",
        )
        super().__init__(**kwargs)

    def on_attack(self, game: "GameState") -> None:
        """Whenever this creature attacks, you gain 1 life."""
        controller = self.controller or self.owner
        if controller is not None:
            controller.gain_life(1)

    def can_activate_graveyard_ability(self, game: "GameState") -> bool:
        """Check if this card is in the graveyard."""
        owner = self.controller or self.owner
        if owner is None:
            return False
        return self in owner.zones[Zone.GRAVEYARD].get_all()

    def activate_graveyard_ability(self, game: "GameState") -> None:
        """{B}{G}: Return this card from graveyard to battlefield tapped."""
        owner = self.controller or self.owner
        if owner is None:
            return
        graveyard = owner.zones[Zone.GRAVEYARD]
        if self in graveyard.get_all():
            graveyard.remove(self)
            self.is_tapped = True
            game.get_battlefield(owner).add(self)
