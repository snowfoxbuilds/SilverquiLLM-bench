"""Card implementation for Render Speechless."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RenderSpeechless(Sorcery):
    """Render Speechless — {2}{W}{B} — Sorcery.

    Target opponent reveals their hand. You choose a nonland card from it.
    That player discards that card.
    Put two +1/+1 counters on up to one target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Render Speechless")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target opponent reveals their hand. You choose a nonland card from it. "
            "That player discards that card.\n"
            "Put two +1/+1 counters on up to one target creature.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Requires an opponent target and optionally a creature target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Reveal hand, discard nonland, put counters on creature."""
        from engine.game import add_counter, discard

        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        # First target: opponent
        opponent = targets[0]

        # Reveal hand and choose a nonland card to discard
        hand = game.get_hand(opponent)
        hand_cards = hand.get_all()
        # Find a nonland card
        nonland_card = None
        for card in hand_cards:
            card_types = getattr(card, "card_types", set())
            if CardType.LAND not in card_types:
                nonland_card = card
                break

        if nonland_card is not None:
            discard(game, opponent, nonland_card)

        # Second target (optional): creature for +1/+1 counters
        if len(targets) >= 2:
            creature = targets[1]
            if creature is not None:
                add_counter(game, creature, "+1/+1", 2)
