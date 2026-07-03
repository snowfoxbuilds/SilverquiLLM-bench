"""Card implementation for Unsubtle Mockery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class UnsubtleMockery(Instant):
    """Unsubtle Mockery — {2}{R} — Instant.

    Unsubtle Mockery deals 4 damage to target creature. Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Unsubtle Mockery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Unsubtle Mockery deals 4 damage to target creature. Surveil 1.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Deal 4 damage to target creature, then surveil 1."""
        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None

        if target is None:
            return

        # Deal 4 damage
        target.damage_taken = getattr(target, "damage_taken", 0) + 4

        # Surveil 1
        if controller is None:
            return
        library = game.get_library(controller)
        lib_cards = library.get_all()
        if lib_cards:
            top_card = lib_cards[-1]
            put_in_gy = True
            if hasattr(controller, "choose_yes_no"):
                try:
                    put_in_gy = controller.choose_yes_no(
                        f"Surveil: Put {getattr(top_card, 'name', 'card')} into your graveyard?"
                    )
                except Exception:
                    put_in_gy = True
            if put_in_gy:
                library.remove(top_card)
                game.get_graveyard(controller).add(top_card)
