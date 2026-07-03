"""Card implementation for Ancestral Anger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AncestralAnger(Sorcery):
    """Ancestral Anger — {R} — Sorcery.

    Target creature gains trample and gets +X/+0 until end of turn,
    where X is 1 plus the number of cards named Ancestral Anger in your graveyard.
    Draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ancestral Anger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Count copies of Ancestral Anger in controller's graveyard
        controller = self.controller or self.owner
        graveyard = game.get_graveyard(controller)
        count = sum(1 for c in graveyard if getattr(c, "name", "") == "Ancestral Anger")

        x = 1 + count

        # Grant trample
        target.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.TRAMPLE

        # +X/+0
        target.modified_power = target.modified_power + x

        # Draw a card
        from engine.game import draw_card
        draw_card(game, controller)
