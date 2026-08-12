"""Card implementation for Liliana, Dreadhorde General."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry

class LilianaDreadhordeGeneral(Planeswalker):
    """Liliana, Dreadhorde General — {4}{B}{B} — 6 loyalty.

    Whenever a creature you control dies, draw a card.
    +1: Create a 2/2 black Zombie creature token.
    -4: Each player sacrifices two creatures of their choice.
    -9: Each opponent chooses a permanent they control of each permanent type
        and sacrifices the rest.

    Phase H implements the +1 Zombie-token minter (grpId 94170). The passive
    dies-trigger draw and the -4/-9 abilities remain simplified stubs (not
    token-related, out of Phase H scope).
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
            "Whenever a creature you control dies, draw a card.\n"
            "+1: Create a 2/2 black Zombie creature token.\n"
            "-4: Each player sacrifices two creatures of their choice.\n"
            "-9: Each opponent chooses a permanent they control of each "
            "permanent type and sacrifices the rest.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            # +1: Create a 2/2 black Zombie creature token.
            from engine.game import create_token

            from cards.fdn.tokens import make_creature_token
            from engine.types import Color

            controller = getattr(pw, "controller", None)
            if controller is None:
                return
            create_token(
                game,
                controller,
                make_creature_token("Zombie", {"Zombie"}, [Color.BLACK], 2, 2),
            )

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
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Create a 2/2 black Zombie creature token."),
            LoyaltyAbility(loyalty_cost=-4, effect=_minus4, description="-4: Draw/discard based on creatures."),
            LoyaltyAbility(loyalty_cost=-9, effect=_minus9, description="-9: Opponents keep one of each type, sacrifice rest."),
        ]
