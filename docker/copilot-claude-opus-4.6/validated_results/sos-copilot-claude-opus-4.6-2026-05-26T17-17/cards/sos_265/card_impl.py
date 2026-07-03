"""Card implementation for Terramorphic Expanse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ActivatedAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TerramorphicExpanse(Land):
    """Terramorphic Expanse — Land.

    {T}, Sacrifice this land: Search your library for a basic land card,
    put it onto the battlefield tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Terramorphic Expanse")
        super().__init__(**kwargs)
        self.mana_cost = None

    def get_mana_abilities(self) -> list:
        """No mana abilities."""
        return []

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            if not check_only:
                source.is_tapped = True
                # Sacrifice: remove from battlefield
                if player is not None and game is not None:
                    battlefield = game.get_battlefield(player)
                    if battlefield.contains(source):
                        battlefield.remove(source)
                        graveyard = game.get_graveyard(player)
                        graveyard.add(source)
                        source.zone = Zone.GRAVEYARD
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            """Search library for a basic land, put it onto battlefield tapped."""
            if player is None or game is None:
                return
            library = player.zones[Zone.LIBRARY]
            lib_cards = list(library.get_all())
            # Find a basic land
            basic_land = None
            for card in lib_cards:
                supertypes = getattr(card, "supertypes", set()) or set()
                card_types = getattr(card, "card_types", set()) or set()
                if "Basic" in supertypes and CardType.LAND in card_types:
                    basic_land = card
                    break
            if basic_land is not None:
                library.remove(basic_land)
                battlefield = game.get_battlefield(player)
                battlefield.add(basic_land)
                basic_land.zone = Zone.BATTLEFIELD
                basic_land.is_tapped = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Sacrifice this land: Search for a basic land, put it onto the battlefield tapped.",
        )]
