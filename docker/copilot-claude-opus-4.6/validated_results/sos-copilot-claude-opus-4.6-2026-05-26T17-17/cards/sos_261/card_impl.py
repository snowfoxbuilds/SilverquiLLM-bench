"""Card implementation for Skycoach Waypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SkycoachWaypoint(Land):
    """Skycoach Waypoint — Land.

    {T}: Add {C}.
    {3}, {T}: Target creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skycoach Waypoint")
        super().__init__(**kwargs)
        self.mana_cost = None

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

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            if not check_only:
                source.is_tapped = True
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            targets = kwargs.get("targets", [])
            if targets:
                target = targets[0]
                target.is_prepared = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}, {T}: Target creature becomes prepared.",
        )]
