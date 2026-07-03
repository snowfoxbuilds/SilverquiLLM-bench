"""Card implementation for Eternal Student."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EternalStudent(Creature):
    """Eternal Student — {3}{B} — Creature — Zombie Warlock.

    4/2. {1}{B}, Exile this card from your graveyard: Create two 1/1 white
    and black Inkling creature tokens with flying.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eternal Student")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Zombie", "Warlock"})
        super().__init__(**kwargs)

    def activate_ability(self, game: "GameState", ability_index: int = 0) -> None:
        """Activate from graveyard: exile self, create two Inkling tokens."""
        owner = self.owner

        # Remove from graveyard
        gy = game.get_graveyard(owner)
        if gy.contains(self):
            gy.remove(self)

        # Move to exile
        game.get_exile(owner).add(self)

        # Create two 1/1 Inkling tokens with flying
        bf = game.get_battlefield(owner)
        for _ in range(2):
            token = Creature(
                name="Inkling",
                owner=owner,
                controller=owner,
                base_power=1,
                base_toughness=1,
                card_types={CardType.CREATURE},
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            token.is_token = True
            bf.add(token)
