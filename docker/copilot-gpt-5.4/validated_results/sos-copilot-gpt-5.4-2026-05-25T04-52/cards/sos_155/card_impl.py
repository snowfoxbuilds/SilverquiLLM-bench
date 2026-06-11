"""Card implementation for Noxious Newt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class NoxiousNewt(Creature):
    """Noxious Newt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Noxious Newt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Salamander"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:  # noqa: ARG001
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True

        def _mana_produced(game: GameState) -> None:  # noqa: ARG001
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.GREEN, 1)

        return [
            ManaAbility(
                cost=_cost,
                mana_produced=_mana_produced,
                description="{T}: Add {G}.",
            )
        ]
