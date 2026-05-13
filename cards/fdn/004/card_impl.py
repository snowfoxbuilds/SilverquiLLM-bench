"""Card implementation for Mountain."""

from __future__ import annotations


from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


def _tap_cost(game: GameState, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap.

    Mirrors :func:`engine.abilities.tap_cost` logic so basic lands
    can be activated through the abilities system or directly.
    """
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class Mountain(Land):
    """Basic Mountain — taps for {R}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Mountain"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {R}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {R}.",
            )
        ]


__all__ = ["Mountain"]
