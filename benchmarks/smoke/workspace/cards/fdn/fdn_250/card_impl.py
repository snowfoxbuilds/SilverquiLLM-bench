"""Card implementation for Burnished Hart."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class BurnishedHart(ArtifactCreature):
    """Burnished Hart — {3} — 2/2 — Elk

    {3}, Sacrifice this creature: Search your library for up to two basic
    land cards, put them onto the battlefield tapped, then shuffle.

    FDN collector number 250.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burnished Hart")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", {"Elk"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{3}, Sacrifice this creature: Search your library for up to "
            "two basic land cards, put them onto the battlefield tapped, "
            "then shuffle.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            controller.mana_pool.pay(ManaCost(generic=3))
            # Sacrifice self
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.card_queries import choose_object

            controller = source.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            # A basic land is a Land with the Basic supertype (there is no
            # `is_basic_land` flag — the earlier filter matched nothing).
            basics = [
                card
                for card in library.get_all()
                if Supertype.BASIC in getattr(card, "supertypes", set())
                and CardType.LAND in getattr(card, "card_types", set())
            ]
            # "Search for UP TO TWO basic land cards" — a declinable choice of
            # 0, 1, or 2 (min=0, max=2), not an automatic grab of the first two.
            found = []
            if basics:
                chosen = choose_object(
                    game,
                    controller,
                    basics,
                    "Search your library for up to two basic land cards",
                    source_card=source,
                    min=0,
                    max=2,
                )
                found = chosen if isinstance(chosen, list) else ([chosen] if chosen else [])
            for basic in found:
                library.remove(basic)
                basic.is_tapped = True
                basic.controller = controller
                bf = game.get_battlefield(controller)
                bf.add(basic)
            if len(library) > 0:
                library.shuffle()

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}, Sacrifice this creature: Search your library "
            "for up to two basic land cards, put them onto the battlefield "
            "tapped, then shuffle.",
        )]
