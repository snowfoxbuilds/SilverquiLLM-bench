"""Card implementation for Summoned Dromedary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SummonedDromedary(Creature):
    """Summoned Dromedary — {3}{W} — 4/3 Spirit Camel with Vigilance.

    {1}{W}: Return this card from your graveyard to your hand.
    Activate only as a sorcery.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Summoned Dromedary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Spirit", "Camel"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        card = self

        def _cost(game: "GameState") -> bool:
            return True

        def _effect(game: "GameState") -> None:
            controller = card.controller
            if controller is None:
                return
            # Remove from graveyard
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(card):
                graveyard.remove(card)
            # Add to hand
            game.get_hand(controller).add(card)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{W}: Return this card from your graveyard to your hand. Activate only as a sorcery.",
        )]
