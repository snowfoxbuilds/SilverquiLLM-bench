"""Card implementation for End of the Hunt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EndOfTheHunt(Sorcery):
    """End of the Hunt — {1}{B} — Sorcery.

    Target opponent exiles a creature or planeswalker they control with the
    greatest mana value among creatures and planeswalkers they control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "End of the Hunt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        opponent = chosen[0]

        bf = game.get_battlefield(opponent)
        candidates = []
        for card in bf.get_all():
            types = getattr(card, "card_types", set())
            if CardType.CREATURE in types or CardType.PLANESWALKER in types:
                candidates.append(card)

        if not candidates:
            return

        # Find greatest mana value
        max_mv = max(getattr(c, "mana_cost", ManaCost()).cmc for c in candidates)
        tied = [c for c in candidates if getattr(c, "mana_cost", ManaCost()).cmc == max_mv]

        # Opponent chooses (we pick first for simplicity)
        to_exile = tied[0]
        bf.remove(to_exile)
        game.get_exile(opponent).add(to_exile)
