"""Card implementation for Island."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class Island(Land):
    """Island — Basic Land — Island. ({T}: Add {U}.)

    FDN collector number 274.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Island")
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Island"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_blue(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.BLUE, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_blue,
                description="{T}: Add {U}.",
            )
        ]
