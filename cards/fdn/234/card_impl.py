"""Card implementation for Vivien Reid."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry

class VivienReid(Planeswalker):
    """Vivien Reid — {3}{G}{G} — 5 loyalty.

    +1: Look at the top four cards. May reveal a creature or land and put
        it into your hand. Rest on bottom.
    −3: Destroy target artifact, enchantment, or creature with flying.
    −8: Emblem — creatures you control get +2/+2 and have vigilance,
        trample, and indestructible.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vivien Reid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("starting_loyalty", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vivien"}
        kwargs.setdefault(
            "rules_text",
            "+1: Look at the top four cards of your library. You may reveal a "
            "creature or land card from among them and put it into your hand. "
            "Put the rest on the bottom of your library in a random order.\n"
            "−3: Destroy target artifact, enchantment, or creature with flying.\n"
            "−8: You get an emblem with \"Creatures you control get +2/+2 and have "
            "vigilance, trample, and indestructible.\"",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Look at top 4 cards, may take a creature or land."""
            import random
            from engine.types import Zone
            controller = pw.controller
            if controller is not None:
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                if len(library) > 0:
                    top_cards = library.get_all()[-4:]
                    found = None
                    # Simplified: take the first creature or land found
                    for card in reversed(top_cards):
                        card_types = getattr(card, "card_types", set())
                        if CardType.CREATURE in card_types or CardType.LAND in card_types:
                            found = card
                            break
                    if found is not None:
                        library.remove(found)
                        hand.add(found)
                        top_cards = [c for c in top_cards if c is not found]
                    # Put remaining looked-at cards on the bottom in random order
                    remaining = [c for c in top_cards if library.contains(c)]
                    for c in remaining:
                        library.remove(c)
                    random.shuffle(remaining)
                    for c in remaining:
                        library.add(c, position="bottom")

        def _minus3(game: Any) -> None:
            """Destroy target artifact, enchantment, or creature with flying."""
            from engine.game import destroy
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                destroy(game, target)

        def _minus8(game: Any) -> None:
            """Emblem — creatures get +2/+2, vigilance, trample, indestructible."""
            # ENGINE LIMITATION: emblem system not implemented — applies one-time buff to current creatures only
            controller = pw.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.base_power += 2
                        obj.base_toughness += 2
                        obj.keywords = (
                            getattr(obj, "keywords", Keyword(0))
                            | Keyword.VIGILANCE
                            | Keyword.TRAMPLE
                            | Keyword.INDESTRUCTIBLE
                        )

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Look at top 4, may take creature or land.",
            ),
            LoyaltyAbility(
                loyalty_cost=-3,
                effect=_minus3,
                description="−3: Destroy target artifact, enchantment, or flyer.",
            ),
            LoyaltyAbility(
                loyalty_cost=-8,
                effect=_minus8,
                description="−8: Emblem — +2/+2, vigilance, trample, indestructible.",
            ),
        ]
