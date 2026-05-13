"""Card implementation for ChandraTorchOfDefiance."""

from __future__ import annotations


from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class ChandraTorchOfDefiance(Planeswalker):
    """Chandra, Torch of Defiance — {2}{R}{R} — 4 loyalty.

    +1: Exile the top card of your library. You may cast that card.
        If you don't, Chandra deals 2 damage to each opponent.
    +1: Add {R}{R}.
    -3: Chandra deals 4 damage to target creature.
    -7: You get an emblem with "Whenever you cast a spell, this emblem
        deals 5 damage to any target."

    (Simplified: abilities are stubs that adjust loyalty only.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chandra, Torch of Defiance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("starting_loyalty", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Chandra"}
        kwargs.setdefault(
            "rules_text",
            "+1: Exile top card, may cast or deal 2 to opponents.\n"
            "+1: Add {R}{R}.\n"
            "-3: Deal 4 damage to target creature.\n"
            "-7: Emblem — whenever you cast a spell, deal 5 to any target.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_exile(game: Any) -> None:
            # Exile top card, may cast or deal 2 to opponents.
            from engine.game import deal_damage
            controller = pw.controller
            if controller is not None:
                # Simplified: deal 2 damage to each opponent
                for p in game.players:
                    if p is not controller:
                        deal_damage(game, pw, p, 2)

        def _plus1_mana(game: Any) -> None:
            # Add {R}{R}.
            controller = pw.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 2)

        def _minus3(game: Any) -> None:
            # Deal 4 damage to target creature.
            from engine.game import deal_damage
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                deal_damage(game, pw, target, 4)

        def _minus7(game: Any) -> None:
            # Emblem — deal 5 on spell cast (simplified: no-op emblem stub).
            pass

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_exile, description="+1: Exile top card, may cast or deal 2."),
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_mana, description="+1: Add {R}{R}."),
            LoyaltyAbility(loyalty_cost=-3, effect=_minus3, description="-3: Deal 4 damage to target creature."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Emblem — deal 5 on spell cast."),
        ]


__all__ = ["ChandraTorchOfDefiance"]
