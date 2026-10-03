"""Card implementation for Goblin Negotiation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GoblinNegotiation(Sorcery):
    """Goblin Negotiation — {X}{R}{R} — Sorcery.

    Goblin Negotiation deals X damage to target creature. Create a number
    of 1/1 red Goblin creature tokens equal to the amount of excess damage
    dealt to that creature this way.

    FDN collector number 88.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Negotiation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{R}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Goblin Negotiation deals X damage to target creature. Create "
            "a number of 1/1 red Goblin creature tokens equal to the amount "
            "of excess damage dealt to that creature this way.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Deal X damage, create Goblin tokens for excess damage."""
        from cards.fdn.tokens import make_creature_token
        from engine.game import create_token, deal_damage

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        controller = self.controller
        if controller is None:
            return

        x_value = getattr(self, "x_value", 0)

        # Calculate toughness remaining before damage (use current toughness)
        toughness = getattr(target, "toughness", getattr(target, "base_toughness", 0))
        damage_already = getattr(target, "damage_marked", 0)
        remaining_toughness = toughness - damage_already

        # Deal X damage
        deal_damage(game, self, target, x_value)

        # Excess damage = X - remaining_toughness (if positive)
        excess = max(0, x_value - remaining_toughness)

        # Create Goblin tokens for excess
        for _ in range(excess):
            token = make_creature_token("Goblin", {"Goblin"}, [Color.RED], 1, 1)
            create_token(game, controller, token)
