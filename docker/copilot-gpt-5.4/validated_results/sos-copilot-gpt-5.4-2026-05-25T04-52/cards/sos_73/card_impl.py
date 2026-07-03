"""Card implementation for Arcane Omens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.game import discard
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArcaneOmens(Sorcery):
    """Arcane Omens."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Omens")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Target player discards X cards, where X is the number of colors of mana "
            "spent to cast this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if not isinstance(target, Player):
            return

        discard_count = len(set(getattr(self, "colors_spent", [])))
        hand = game.get_hand(target)
        for _ in range(min(discard_count, len(hand))):
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                break
            chosen = target.choose_card(cards_in_hand, "Choose a card to discard for Arcane Omens")
            if chosen not in cards_in_hand:
                chosen = cards_in_hand[0]
            discard(game, target, chosen)
