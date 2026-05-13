"""Card implementation for Liliana, Dreadhorde General."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard, draw_card, sacrifice
from engine.types import CardType, ManaCost, Supertype


class LilianaDreadhordeGeneral(Planeswalker):
    """Liliana, Dreadhorde General — {4}{B}{B} — 6 loyalty.

    +1: Each opponent sacrifices a creature.
    -4: Each player draws cards equal to the number of creatures they control,
        then each opponent discards that many cards.
    -9: Each opponent chooses a permanent they control of each permanent type
        and sacrifices the rest.

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Liliana, Dreadhorde General")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 6)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Liliana"}
        kwargs.setdefault(
            "rules_text",
            "+1: Each opponent sacrifices a creature.\n"
            "-4: Each player draws cards equal to creatures they control, "
            "then each opponent discards that many.\n"
            "-9: Each opponent keeps one of each permanent type, sacrifices the rest.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            # Each opponent sacrifices a creature.
            from engine.game import sacrifice
            for p in game.players:
                if p is not pw.controller:
                    from engine.types import CardType as CT
                    bf = game.get_battlefield(p)
                    for obj in bf.get_all():
                        if CT.CREATURE in getattr(obj, "card_types", set()):
                            sacrifice(game, p, obj)
                            break

        def _minus4(game: Any) -> None:
            # Each player draws cards equal to creatures they control.
            from engine.game import draw_card
            from engine.types import CardType as CT
            for p in game.players:
                bf = game.get_battlefield(p)
                count = sum(1 for obj in bf.get_all() if CT.CREATURE in getattr(obj, "card_types", set()))
                for _ in range(count):
                    draw_card(game, p)

        def _minus9(game: Any) -> None:
            # Opponents keep one of each permanent type, sacrifice rest (simplified stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Each opponent sacrifices a creature."),
            LoyaltyAbility(loyalty_cost=-4, effect=_minus4, description="-4: Draw/discard based on creatures."),
            LoyaltyAbility(loyalty_cost=-9, effect=_minus9, description="-9: Opponents keep one of each type, sacrifice rest."),
        ]
