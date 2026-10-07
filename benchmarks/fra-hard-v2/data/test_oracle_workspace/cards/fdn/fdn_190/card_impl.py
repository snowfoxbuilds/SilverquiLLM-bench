"""Card implementation for Brass's Bounty."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BrasssBountyAbility1:
    text = 'For each land you control, create a Treasure token. (It\'s an artifact with "{T}, Sacrifice this token: Add one mana of any color.")'


# endregion Printed abilities


class BrasssBounty(Sorcery):
    """Brass's Bounty — {6}{R} — Sorcery.

    For each land you control, create a Treasure token.

    FDN collector number 190.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brass's Bounty")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{R}"))
        kwargs.setdefault(
            "rules_text",
            "For each land you control, create a Treasure token.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Create a Treasure token for each land you control."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        bf = game.get_battlefield(controller)
        land_count = 0
        for perm in bf.get_all():
            if CardType.LAND in getattr(perm, "card_types", set()):
                land_count += 1

        from cards.fdn.tokens import make_treasure_token

        # create_token no-ops for count <= 0, so no zero-land guard is needed.
        create_token(
            game, controller, factory=make_treasure_token, count=land_count
        )
