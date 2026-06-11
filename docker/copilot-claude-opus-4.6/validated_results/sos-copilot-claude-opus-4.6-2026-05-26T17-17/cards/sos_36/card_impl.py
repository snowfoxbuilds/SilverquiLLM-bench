"""Card implementation for Stone Docent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StoneDocent(Creature):
    """Stone Docent — {1}{W} — 3/1 Spirit Chimera.

    {W}, Exile this card from your graveyard: You gain 2 life. Surveil 1.
    Activate only as a sorcery.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stone Docent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Spirit", "Chimera"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        card = self

        def _cost(game: "GameState") -> bool:
            return True

        def _effect(game: "GameState") -> None:
            controller = card.controller
            if controller is None:
                return
            # Exile from graveyard
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(card):
                graveyard.remove(card)
                game.get_exile(controller).add(card)
            # Gain 2 life
            controller.life += 2
            # Surveil 1
            library = game.get_library(controller)
            cards = library.get_all()
            if cards:
                top_card = cards[-1]
                # Default: put into graveyard (surveil choice)
                library.remove(top_card)
                game.get_graveyard(controller).add(top_card)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{W}, Exile this card from your graveyard: You gain 2 life. Surveil 1. Activate only as a sorcery.",
        )]
