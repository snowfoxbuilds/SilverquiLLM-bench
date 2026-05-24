"""Card implementation for Spectral Sailor."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from cards.registry import CardRegistry

class SpectralSailor(Creature):
    """Spectral Sailor — {U} — 1/1 — Spirit Pirate

    Flash
    Flying
    {3}{U}: Draw a card.

    FDN collector number 164.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spectral Sailor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Spirit", "Pirate"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying\n{3}{U}: Draw a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            if controller.mana_pool.get(ManaType.BLUE) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{3}{U}"))
            return True

        def _effect(game: Any) -> None:
            from benchmarks.sos.workspace.engine.game import draw_card

            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}{U}: Draw a card.",
        )]
