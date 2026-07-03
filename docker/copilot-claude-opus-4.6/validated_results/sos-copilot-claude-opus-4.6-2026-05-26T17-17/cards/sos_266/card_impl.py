"""Card implementation for Titan's Grave."""

from __future__ import annotations

from typing import Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaType, Zone


class TitansGrave(Land):
    """Titan's Grave — Land.

    This land enters tapped.
    {T}: Add {B} or {G}.
    {2}{B}{G}, {T}: Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Titan's Grave")
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

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            source.is_tapped = True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            """Surveil 1: look at top card of library, may put into graveyard."""
            if player is None:
                return
            library = player.zones[Zone.LIBRARY]
            lib_cards = list(library.get_all())
            if not lib_cards:
                return
            # Top card is last in list
            top_card = lib_cards[-1]
            # Default: put into graveyard
            library.remove(top_card)
            player.zones[Zone.GRAVEYARD].add(top_card)
            if hasattr(top_card, 'zone'):
                top_card.zone = Zone.GRAVEYARD

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{B}{G}, {T}: Surveil 1.",
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """This land enters tapped."""
        self.is_tapped = True

