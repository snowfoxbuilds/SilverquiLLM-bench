"""Card implementation for Dig Site Inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DigSiteInventory(Sorcery):
    """{W} Sorcery — +1/+1 counter and vigilance until EOT. Flashback {W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dig Site Inventory")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import add_counter

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # +1/+1 counter
        add_counter(game, target, "+1/+1", 1)

        # Grant vigilance
        target.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.VIGILANCE
