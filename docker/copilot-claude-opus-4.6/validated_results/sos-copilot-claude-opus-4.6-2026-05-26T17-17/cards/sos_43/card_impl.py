"""Card implementation for Divergent Equation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DivergentEquation(Instant):
    """Divergent Equation — {X}{X}{U} — Instant.

    Return up to X target instant and/or sorcery cards from your graveyard
    to your hand. Exile Divergent Equation.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Divergent Equation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{X}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return up to X target instant and/or sorcery cards from your "
            "graveyard to your hand.\nExile Divergent Equation.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target up to X instant/sorcery cards in your graveyard."""
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    (CardType.INSTANT in getattr(obj, "card_types", set())
                     or CardType.SORCERY in getattr(obj, "card_types", set()))
                    and getattr(obj, "owner", None) is controller
                ),
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return chosen targets to hand, then exile self."""
        chosen = getattr(self, "chosen_targets", None) or []
        controller = self.controller

        # Return each target from graveyard to hand
        for target in chosen:
            gy = game.get_graveyard(controller)
            if gy.contains(target):
                gy.remove(target)
                game.get_hand(controller).add(target)

        # Exile Divergent Equation itself
        game.get_exile(controller).add(self)
