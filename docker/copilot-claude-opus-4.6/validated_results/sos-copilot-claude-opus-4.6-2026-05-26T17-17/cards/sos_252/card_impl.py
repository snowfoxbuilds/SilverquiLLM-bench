"""Card implementation for Strixhaven Skycoach."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StrixhavenSkycoach(Artifact):
    """Strixhaven Skycoach — {3} — Artifact — Vehicle 3/2.

    Flying
    When this Vehicle enters, you may search your library for a basic land card,
    reveal it, put it into your hand, then shuffle.
    Crew 2
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strixhaven Skycoach")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", {"Vehicle"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this Vehicle enters, you may search your library for a basic land card, "
            "reveal it, put it into your hand, then shuffle.\nCrew 2",
        )
        self._is_creature: bool = False
        super().__init__(**kwargs)
        self.base_power: int = 3
        self.base_toughness: int = 2
        self.crew_cost: int = 2

    @property
    def card_types(self) -> set:
        types = self._card_types.copy() if hasattr(self, '_card_types') else {CardType.ARTIFACT}
        if self._is_creature:
            types.add(CardType.CREATURE)
        return types

    @card_types.setter
    def card_types(self, value: set) -> None:
        self._card_types = value

    def crew(self, game: Any, player: Any) -> None:
        """Crew this vehicle, making it an artifact creature until end of turn."""
        self._is_creature = True

    def on_enter_battlefield(self, game: Any, may_choice: bool = True) -> None:
        """ETB: You may search your library for a basic land card."""
        if not may_choice:
            return
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        # Search for a basic land
        all_cards = library.get_all()
        basic_land = None
        for card in all_cards:
            is_land = CardType.LAND in getattr(card, "card_types", set()) or isinstance(card, Land)
            is_basic = "Basic" in getattr(card, "supertypes", set())
            if is_land and is_basic:
                basic_land = card
                break
        if basic_land is not None:
            library.remove(basic_land)
            controller.zones[Zone.HAND].add(basic_land)

