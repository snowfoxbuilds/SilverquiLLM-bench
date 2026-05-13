"""Card implementation for KaitoCunningInfiltrator."""

from __future__ import annotations


from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class KaitoCunningInfiltrator(Planeswalker):
    """Kaito, Cunning Infiltrator — {1}{U}{U} — 3 loyalty.

    Whenever a creature you control deals combat damage to a player, put a
    loyalty counter on Kaito.
    +1: Up to one target creature you control can't be blocked this turn.
        Draw a card, then discard a card.
    −2: Create a 2/1 blue Ninja creature token.
    −9: You get an emblem with "Whenever a player casts a spell, you create
        a 2/1 blue Ninja creature token."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kaito, Cunning Infiltrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Kaito"}
        kwargs.setdefault(
            "rules_text",
            "Whenever a creature you control deals combat damage to a player, "
            "put a loyalty counter on Kaito.\n"
            "+1: Up to one target creature you control can't be blocked this turn. "
            "Draw a card, then discard a card.\n"
            "−2: Create a 2/1 blue Ninja creature token.\n"
            "−9: You get an emblem with \"Whenever a player casts a spell, you "
            "create a 2/1 blue Ninja creature token.\"",
        )
        super().__init__(**kwargs)

    # ENGINE LIMITATION: combat damage trigger for loyalty counters not implemented — requires combat damage events

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Up to one target creature can't be blocked. Draw then discard."""
            from engine.game import draw_card
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                target._cant_be_blocked = True  # type: ignore[attr-defined]
            controller = pw.controller
            if controller is not None:
                draw_card(game, controller)
                # Discard: remove last card from hand if any
                from engine.types import Zone
                hand = controller.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if cards_in_hand:
                    card_to_discard = cards_in_hand[-1]
                    hand.remove(card_to_discard)
                    gy = controller.zones[Zone.GRAVEYARD]
                    gy.add(card_to_discard)

        def _minus2(game: Any) -> None:
            """Create a 2/1 blue Ninja creature token."""
            from engine.game import create_token
            controller = pw.controller
            if controller is not None:
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

        def _minus9(game: Any) -> None:
            """Emblem — whenever a player casts a spell, create a 2/1 Ninja token."""
            # ENGINE LIMITATION: emblem system not implemented — creates a single Ninja token as approximation
            from engine.game import create_token
            controller = pw.controller
            if controller is not None:
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Target creature can't be blocked. Draw, then discard.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Create a 2/1 blue Ninja creature token.",
            ),
            LoyaltyAbility(
                loyalty_cost=-9,
                effect=_minus9,
                description="−9: Emblem — spell cast → create 2/1 Ninja token.",
            ),
        ]


__all__ = ["KaitoCunningInfiltrator"]
