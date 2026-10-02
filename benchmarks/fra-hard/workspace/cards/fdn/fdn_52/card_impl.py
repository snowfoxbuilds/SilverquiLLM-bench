"""Card implementation for Strix Lookout."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class StrixLookout(Creature):
    """Strix Lookout — {1}{U} — 1/2 — Bird

    Flying, vigilance
    {1}{U}, {T}: Draw a card, then discard a card.

    FDN collector number 52.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strix Lookout")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Bird"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n{1}{U}, {T}: Draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 2:
                return False
            controller.mana_pool.pay(ManaCost.parse("{1}{U}"))
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import draw_card, discard

            controller = source.controller
            if controller is None:
                return
            drawn = draw_card(game, controller)
            # Discard a card (simplified: discard the drawn card if any,
            # or the last card in hand)
            hand = controller.zones[Zone.HAND]
            if len(hand) > 0:
                to_discard = hand.cards[-1] if hasattr(hand, "cards") else hand.get_all()[-1]
                discard(game, controller, to_discard)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{U}, {T}: Draw a card, then discard a card.",
        )]
