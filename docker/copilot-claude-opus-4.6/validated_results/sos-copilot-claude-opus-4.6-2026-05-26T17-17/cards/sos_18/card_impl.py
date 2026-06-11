"""Card implementation for Harsh Annotation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class HarshAnnotation(Instant):
    """Harsh Annotation — {1}{W} — Instant.

    Destroy target creature. Its controller creates a 1/1 white and black
    Inkling creature token with flying.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Harsh Annotation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target creature. Its controller creates a 1/1 white "
            "and black Inkling creature token with flying.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy target creature, its controller gets a 1/1 Inkling with flying."""
        from engine.game import create_token, destroy

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Remember the controller of the target before destroying
        target_controller = getattr(target, "controller", None)

        # Destroy target creature
        destroy(game, target)

        # Its controller creates a 1/1 white and black Inkling with flying
        if target_controller is not None:
            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                owner=target_controller,
                controller=target_controller,
            )
            token.colors = {"W", "B"}
            create_token(game, target_controller, token)

