"""Card implementation for Stormcarved Coast."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StormcarvedCoast(Land):
    """Stormcarved Coast — Land.

    This land enters tapped unless you control two or more other lands.
    {T}: Add {U} or {R}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stormcarved Coast")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {U} or {R}.",
            mana_types=[ManaType.BLUE, ManaType.RED],
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """Enters tapped unless controller has two or more other lands."""
        controller = self.controller
        if controller is None:
            self.is_tapped = True
            return
        battlefield = game.get_battlefield(controller)
        all_permanents = battlefield.get_all()
        other_lands = [
            p for p in all_permanents
            if p is not self and CardType.LAND in getattr(p, "card_types", set())
        ]
        if len(other_lands) < 2:
            self.is_tapped = True
        else:
            self.is_tapped = False
