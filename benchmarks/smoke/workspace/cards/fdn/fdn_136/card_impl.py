"""Card implementation for Angel of Finality."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AngelOfFinality(Creature):
    """Angel of Finality — {3}{W} — 3/4 — Angel — Flying.

    When this creature enters, exile target player's graveyard.

    FDN collector number 136.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Angel of Finality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Angel"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, exile target player's graveyard.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """ETB targets a player (whose graveyard is then exiled)."""
        players = list(game.players)
        return [
            TargetRequirement(
                filter_fn=lambda obj: any(obj is p for p in players),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile every card in the target player's graveyard."""
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None or not hasattr(target, "zones"):
            return
        graveyard = target.zones[Zone.GRAVEYARD]
        # Snapshot first — exile mutates the graveyard container as it moves cards.
        for card in list(graveyard.get_all()):
            exile(game, card)
