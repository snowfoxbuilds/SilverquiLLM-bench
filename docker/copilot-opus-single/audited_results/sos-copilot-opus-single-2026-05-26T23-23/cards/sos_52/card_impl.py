"""Card implementation for Harmonized Trio // Brainstorm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, ActivatedAbility
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HarmonizedTrioBrainstorm(Creature):
    """Harmonized Trio // Brainstorm — {U} — 1/1 — Merfolk Bard Wizard.

    {T}, Tap two untapped creatures you control: This creature becomes prepared.
    While prepared, you may cast a copy of Brainstorm. Doing so unprepares it.

    Brainstorm: Draw three cards, then put two cards from your hand on top of
    your library.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Harmonized Trio")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Bard", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{T}, Tap two untapped creatures you control: This creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the prepare ability."""
        return [
            ActivatedAbility(
                cost=self._prepare_cost,
                effect=self._prepare_effect,
                description="{T}, Tap two untapped creatures you control: This creature becomes prepared.",
            )
        ]

    def _get_other_untapped_creatures(self, game: "GameState") -> list[Any]:
        """Get other untapped creatures controlled by this creature's controller."""
        battlefield = game.get_battlefield(self.controller)
        others = []
        for obj in battlefield.get_all():
            if obj is self:
                continue
            if isinstance(obj, Creature) and not getattr(obj, "is_tapped", False):
                if not getattr(obj, "summoning_sick", False):
                    others.append(obj)
        return others

    def _prepare_cost(self, game: "GameState") -> Any:
        """Pay cost: tap self and two other untapped creatures."""
        if self.is_tapped:
            return False

        others = self._get_other_untapped_creatures(game)
        if len(others) < 2:
            return False

        self.is_tapped = True
        others[0].is_tapped = True
        others[1].is_tapped = True
        return True

    def _prepare_effect(self, game: "GameState") -> None:
        """Effect: become prepared."""
        self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Brainstorm: draw 3, put 2 back on top of library."""
        if not self.is_prepared:
            raise RuntimeError("Cannot cast prepared spell: creature is not prepared.")

        player = self.controller
        hand = game.get_hand(player)
        library = game.get_library(player)

        # Draw 3 cards
        for _ in range(3):
            if len(library) > 0:
                all_cards = library.get_all()
                top_card = all_cards[-1]
                library.remove(top_card)
                hand.add(top_card)

        # Put 2 cards from hand on top of library
        hand_cards = hand.get_all()
        cards_to_put_back = hand_cards[:2] if len(hand_cards) >= 2 else hand_cards[:]
        for c in cards_to_put_back:
            hand.remove(c)
            library.add(c, position="top")

        # Unprepare
        self.is_prepared = False
