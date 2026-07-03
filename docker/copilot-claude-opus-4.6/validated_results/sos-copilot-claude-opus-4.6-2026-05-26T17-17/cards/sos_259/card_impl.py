"""Card implementation for Petrified Hamlet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PetrifiedHamlet(Land):
    """Petrified Hamlet — Land.

    When this land enters, choose a land card name.
    Activated abilities of sources with the chosen name can't be activated unless mana abilities.
    Lands with the chosen name have "{T}: Add {C}."
    {T}: Add {C}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Petrified Hamlet")
        super().__init__(**kwargs)
        self.chosen_name: str | None = None

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {C}.",
            mana_types=[ManaType.COLORLESS],
        )]

    def enter_battlefield(self, game: Any, choice: str | None = None, **kwargs: Any) -> None:
        """When this land enters, choose a land card name."""
        if choice is not None:
            self.chosen_name = choice

    def blocks_ability(self, game: Any, source_card: Any, mana_ability: bool = False) -> bool:
        """Check if this Hamlet blocks an ability activation from source_card."""
        if self.chosen_name is None:
            return False
        if getattr(source_card, "name", None) != self.chosen_name:
            return False
        if mana_ability:
            return False
        return True

    def get_granted_mana_abilities(self, game: Any, target_card: Any) -> list[ManaAbility]:
        """Return mana abilities granted to target_card if it has the chosen name."""
        if self.chosen_name is None:
            return []
        if getattr(target_card, "name", None) != self.chosen_name:
            return []

        target = target_card

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            target.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {C}.",
            mana_types=[ManaType.COLORLESS],
        )]
