"""Card implementation for Daydream."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Daydream(Sorcery):
    """{W} Sorcery — Exile target creature you control, return with +1/+1 counter. Flashback {2}{W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Daydream")
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
        from engine.game import add_counter, exile

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        owner = getattr(target, "owner", self.controller)

        # Exile the creature
        exile(game, target)

        # Return to battlefield under owner's control with +1/+1 counter
        # Remove from exile
        exile_zone = owner.zones[Zone.EXILE]
        if exile_zone.contains(target):
            exile_zone.remove(target)

        target.controller = owner
        bf = game.get_battlefield(owner)
        bf.add(target)

        # Add +1/+1 counter
        add_counter(game, target, "+1/+1", 1)
