"""Card implementation for End of the Hunt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.game import exile
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EndOfTheHunt(Sorcery):
    """End of the Hunt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "End of the Hunt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target opponent exiles a creature or planeswalker they control with the greatest "
            "mana value among creatures and planeswalkers they control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player) and obj is not controller,
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if targets else None
        if not isinstance(target_player, Player):
            return

        candidates = [
            permanent
            for permanent in game.get_battlefield(target_player).get_all()
            if isinstance(permanent, (Creature, Planeswalker))
        ]
        if not candidates:
            return

        greatest_mana_value = max(getattr(getattr(card, "mana_cost", None), "cmc", 0) for card in candidates)
        tied = [
            card
            for card in candidates
            if getattr(getattr(card, "mana_cost", None), "cmc", 0) == greatest_mana_value
        ]
        chosen = tied[0]
        if len(tied) > 1:
            try:
                chosen = target_player.choose_card(tied, "creature or planeswalker to exile")
            except Exception:
                chosen = tied[0]
            if chosen not in tied:
                chosen = tied[0]
        if game.get_battlefield(target_player).contains(chosen):
            exile(game, chosen)
