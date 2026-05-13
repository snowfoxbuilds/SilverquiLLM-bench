"""Card implementation for Mountain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState




def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
class Mountain(Land):
    """Basic Mountain — taps for {R}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mountain")
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
