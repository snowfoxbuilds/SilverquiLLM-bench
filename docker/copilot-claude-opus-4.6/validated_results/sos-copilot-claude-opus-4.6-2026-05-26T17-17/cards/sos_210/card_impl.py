"""Card implementation for Practiced Scrollsmith."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PracticedScrollsmith(Creature):
    """Practiced Scrollsmith — {R}{R/W}{W} — 3/2 — Creature — Dwarf Cleric.

    First strike
    When this creature enters, exile target noncreature, nonland card from your graveyard.
    Until the end of your next turn, you may cast that card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Practiced Scrollsmith")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{R/W}{W}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._exiled_card: Any = None

    def on_enter_battlefield(self, game: "GameState", target: Any = None, **kwargs: Any) -> None:
        """ETB: exile target noncreature, nonland card from your graveyard."""
        controller = self.controller
        if target is None:
            return

        # Validate target is noncreature, nonland
        card_types = getattr(target, 'card_types', set())
        if CardType.CREATURE in card_types:
            raise ValueError("Cannot target a creature card.")
        if CardType.LAND in card_types:
            raise ValueError("Cannot target a land card.")

        # Validate target is in controller's graveyard
        if target.owner is not controller:
            raise ValueError("Can only target cards in your own graveyard.")

        # Exile the target
        gy = game.get_graveyard(controller)
        gy.remove(target)
        target.zone = Zone.EXILE
        target.can_be_cast = True
        self._exiled_card = target

    def on_turn_end_cleanup(self, game: "GameState", turns_passed: int = 0, **kwargs: Any) -> None:
        """After end of next turn, the cast permission expires."""
        if turns_passed >= 2 and self._exiled_card is not None:
            self._exiled_card.can_be_cast = False
