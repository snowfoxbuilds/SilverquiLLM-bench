"""Card implementation for Squad Rallier."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SquadRallier(Creature):
    """Squad Rallier — {3}{W} — 3/4 — Human Scout.

    {2}{W}: Look at the top four cards of your library. You may reveal a
    creature card with power 2 or less from among them and put it into
    your hand. Put the rest on the bottom of your library in a random
    order.

    FDN collector number 24.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Squad Rallier")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Scout"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "{2}{W}: Look at the top four cards of your library. You may "
            "reveal a creature card with power 2 or less from among them "
            "and put it into your hand. Put the rest on the bottom of your "
            "library in a random order.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {2}{W} look-at-top-four ability."""
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            # ENGINE LIMITATION: The actual cost is {2}{W} but we use generic {3}
            # because the activated-ability pipeline does not distinguish colored
            # mana requirements from generic for ability costs.
            cost = ManaCost(generic=3)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            from benchmarks.sos.workspace.engine.types import Zone

            library = ctrl.zones[Zone.LIBRARY]
            cards_in_lib = list(library.get_all())
            # Library top is at the end of the list (highest index)
            top_four = cards_in_lib[-4:] if len(cards_in_lib) >= 4 else cards_in_lib[:]
            if not top_four:
                return

            # Remove top four from library
            for card in top_four:
                library.remove(card)

            # Find eligible creature cards (power 2 or less)
            eligible = [
                c for c in top_four
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "base_power", 0) <= 2
            ]

            chosen = None
            if eligible:
                chosen = ctrl.choose_card(
                    eligible,
                    "Choose a creature with power 2 or less to put into "
                    "your hand (or None)",
                )

            if chosen is not None and chosen in top_four:
                top_four.remove(chosen)
                ctrl.zones[Zone.HAND].add(chosen)

            # Put the rest on the bottom in random order
            random.shuffle(top_four)
            for card in top_four:
                library.add(card, position="bottom")

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{W}: Look at top four, may take a creature with power 2 or less.",
        )]
