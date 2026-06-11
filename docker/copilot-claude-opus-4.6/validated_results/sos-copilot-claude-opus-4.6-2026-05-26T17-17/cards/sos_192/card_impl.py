"""Card implementation for Grapple with Death."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GrappleWithDeath(Sorcery):
    """Grapple with Death — {1}{B}{G} — Sorcery.

    Destroy target artifact or creature. You gain 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grapple with Death")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target artifact or creature."""
        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            return CardType.CREATURE in card_types or CardType.ARTIFACT in card_types

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target artifact or creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy target artifact or creature. You gain 1 life."""
        from engine.game import destroy

        chosen = getattr(self, "chosen_targets", [])
        if chosen:
            target = chosen[0]
            if target is not None:
                destroy(game, target)

        # Gain 1 life regardless of whether destruction succeeded
        controller = self.controller
        if controller is not None:
            controller.life += 1
