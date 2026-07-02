"""Card implementation for Mountain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class Mountain(Land):
    """Mountain — Basic Land — Mountain. ({T}: Add {R}.)

    FDN collector number 278.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mountain")
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Mountain"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_red(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_red,
                description="{T}: Add {R}.",
            )
        ]
