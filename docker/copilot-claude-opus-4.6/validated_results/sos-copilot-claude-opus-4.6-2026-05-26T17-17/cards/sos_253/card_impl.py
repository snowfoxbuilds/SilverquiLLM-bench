"""Card implementation for Deathcap Glade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DeathcapGlade(Land):
    """Deathcap Glade — Land.

    This land enters tapped unless you control two or more other lands.
    {T}: Add {B} or {G}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Deathcap Glade")
        kwargs.setdefault(
            "rules_text",
            "This land enters tapped unless you control two or more other lands.\n{T}: Add {B} or {G}.",
        )
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
            description="{T}: Add {B} or {G}.",
            mana_types=[ManaType.BLACK, ManaType.GREEN],
        )]

    def on_enter_battlefield(self, game: Any) -> None:
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

