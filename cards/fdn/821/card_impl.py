"""Card implementation for NissaWorldwaker."""

from __future__ import annotations


from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class NissaWorldwaker(Planeswalker):
    """Nissa, Worldwaker — {3}{G}{G} — 3 loyalty.

    +1: Target land you control becomes a 4/4 Elemental creature with trample.
        It's still a land.
    +1: Untap up to four target Forests.
    -7: Search your library for any number of basic land cards, put them onto
        the battlefield, then shuffle your library. Those lands become 4/4
        Elemental creatures with trample. They're still lands.

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Nissa, Worldwaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Nissa"}
        kwargs.setdefault(
            "rules_text",
            "+1: Target land becomes a 4/4 Elemental with trample.\n"
            "+1: Untap up to four target Forests.\n"
            "-7: Search for basics, put onto battlefield as 4/4 Elementals.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_animate(game: Any) -> None:
            # Target land becomes a 4/4 Elemental with trample (simplified).
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                target.base_power = 4
                target.base_toughness = 4

        def _plus1_untap(game: Any) -> None:
            # Untap up to four Forests (simplified: untap up to 4 lands).
            controller = pw.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                untapped = 0
                for obj in bf.get_all():
                    if untapped >= 4:
                        break
                    if getattr(obj, "is_tapped", False):
                        obj.is_tapped = False
                        untapped += 1

        def _minus7(game: Any) -> None:
            # Search for basics, make 4/4 Elementals (simplified stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_animate, description="+1: Animate a land as 4/4 Elemental."),
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_untap, description="+1: Untap up to four Forests."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Search for basics, make 4/4 Elementals."),
        ]


__all__ = ["NissaWorldwaker"]
