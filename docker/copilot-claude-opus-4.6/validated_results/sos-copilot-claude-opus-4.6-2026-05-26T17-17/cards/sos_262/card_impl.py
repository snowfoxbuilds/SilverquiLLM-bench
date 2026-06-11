"""Card implementation for Spectacle Summit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SpectacleSummit(Land):
    """Spectacle Summit — Land.

    This land enters tapped.
    {T}: Add {U} or {R}.
    {2}{U}{R}, {T}: Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spectacle Summit")
        super().__init__(**kwargs)
        self.mana_cost = None

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """Always enters tapped."""
        self.is_tapped = True

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

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            if not check_only:
                source.is_tapped = True
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            """Surveil 1: look at top card, may put to graveyard."""
            if player is None:
                return
            choice = kwargs.get("choice", "graveyard")
            library = player.zones[Zone.LIBRARY]
            lib_cards = list(library.get_all())
            if not lib_cards:
                return
            top_card = lib_cards[-1]
            if choice == "graveyard":
                library.remove(top_card)
                player.zones[Zone.GRAVEYARD].add(top_card)
                top_card.zone = Zone.GRAVEYARD

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{U}{R}, {T}: Surveil 1.",
        )]
