"""Card implementation for Oracle's Restoration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class OraclesRestoration(Sorcery):
    """Oracle's Restoration — {G} — Sorcery.

    Target creature you control gets +1/+1 until end of turn.
    You draw a card and gain 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Oracle's Restoration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Requires a target creature you control."""
        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            return CardType.CREATURE in card_types

        return [TargetRequirement(
            filter_fn=_filter,
            description="target creature you control",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """Give target +1/+1, draw a card, gain 1 life."""
        targets = getattr(self, "chosen_targets", None) or []
        controller = self.controller

        if targets:
            target = targets[0]
            # +1/+1 until end of turn
            target.modified_power += 1
            target.modified_toughness += 1

        if controller is None:
            return

        # Draw a card
        from engine.game import draw_card
        draw_card(game, controller)

        # Gain 1 life
        controller.life += 1
