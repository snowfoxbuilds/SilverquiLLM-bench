"""Card implementation for Foolish Fate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class FoolishFate(Instant):
    """Foolish Fate — {2}{B} — Instant.

    Destroy target creature.
    Infusion — If you gained life this turn, that creature's controller loses 3 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Foolish Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
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
        if not chosen:
            return
        target = chosen[0]

        # Determine target's controller before destroying
        target_controller = getattr(target, "controller", None) or getattr(target, "owner", None)

        # Destroy target creature (move to graveyard)
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                game.get_graveyard(player).add(target)
                break

        # Infusion: if caster gained life this turn, controller loses 3 life
        caster = self.controller or self.owner
        life_gained = getattr(caster, "life_gained_this_turn", 0)
        if life_gained > 0 and target_controller is not None:
            target_controller.life -= 3
