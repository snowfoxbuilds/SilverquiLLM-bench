"""Card implementation for Forum of Amity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ForumOfAmity(Land):
    """Forum of Amity — Land.

    This land enters tapped.
    {T}: Add {W} or {B}.
    {2}{W}{B}, {T}: Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Forum of Amity")
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
            description="{T}: Add {W} or {B}.",
            mana_types=[ManaType.WHITE, ManaType.BLACK],
        )]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            if source.is_tapped:
                return False
            if not check_only:
                source.is_tapped = True
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, choice: str = "library", **kwargs: Any) -> None:
            controller = player or (source.controller if source else None)
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            all_cards = library.get_all()
            if not all_cards:
                return
            top_card = all_cards[-1]
            if choice == "graveyard":
                library.remove(top_card)
                controller.zones[Zone.GRAVEYARD].add(top_card)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{W}{B}, {T}: Surveil 1.",
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """This land always enters tapped."""
        self.is_tapped = True
