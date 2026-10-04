"""Card implementation for Uncharted Voyage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.card_queries import query_yes_no
from engine.zones import move_to_zone
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class UnchartedVoyageAbility1:
    text = "Target creature's owner puts it on their choice of the top or bottom of their library."


class UnchartedVoyageAbility2:
    text = 'Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)'


# endregion Printed abilities


class UnchartedVoyage(Instant):
    """Uncharted Voyage — {3}{U} — Instant.

    Target creature's owner puts it on their choice of the top or bottom
    of their library.
    Surveil 1.

    FDN collector number 53.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Uncharted Voyage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature's owner puts it on their choice of the top or "
            "bottom of their library.\nSurveil 1.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Put target creature on top or bottom of owner's library, then surveil 1."""
        controller = self.controller
        if controller is None:
            return

        # Get target creature
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None

        # Single-target spell fizzles if target is illegal or left battlefield
        if target is None:
            return
        target_on_bf = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                target_on_bf = True
                break
        if not target_on_bf:
            return

        if target is not None:
            owner = getattr(target, "owner", None)
            if owner is not None:
                # Owner chooses top or bottom
                put_on_top = query_yes_no(
                    game,
                    owner,
                    f"Put {getattr(target, 'name', 'creature')} on top of library? (No = bottom)",
                    source_card=self,
                )
                move_to_zone(
                    game, target, Zone.BATTLEFIELD, Zone.LIBRARY,
                    position="top" if put_on_top else "bottom",
                )

        # Surveil 1
        library = controller.zones[Zone.LIBRARY]
        lib_cards = list(library.get_all())
        if lib_cards:
            top_card = lib_cards[-1]  # Top is end of list
            put_in_gy = query_yes_no(
                game,
                controller,
                f"Surveil: Put {getattr(top_card, 'name', 'card')} into your graveyard?",
                source_card=self,
            )
            if put_in_gy:
                library.remove(top_card)
                controller.zones[Zone.GRAVEYARD].add(top_card)
