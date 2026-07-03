"""Card implementation for Mind Roots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MindRoots(Sorcery):
    """Mind Roots — {1}{B}{G} — Sorcery.

    Target player discards two cards. Put up to one land card discarded this way
    onto the battlefield tapped under your control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mind Roots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Requires a player target."""
        return [TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, 'life'),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """Target player discards two; put up to one land onto BF tapped."""
        if not self.chosen_targets or self.controller is None:
            return
        target_player = self.chosen_targets[0]
        hand = game.get_hand(target_player)

        # Discard up to two cards
        discarded: list[Any] = []
        hand_cards = hand.get_all()
        num_to_discard = min(2, len(hand_cards))
        for i in range(num_to_discard):
            cards = hand.get_all()
            if not cards:
                break
            to_discard = cards[0]
            hand.remove(to_discard)
            discarded.append(to_discard)

        # Find land cards among discarded
        lands_discarded = [c for c in discarded if CardType.LAND in getattr(c, 'card_types', set())]

        # Put up to one land onto battlefield tapped under caster's control
        if lands_discarded:
            land = lands_discarded[0]
            land.is_tapped = True
            land.controller = self.controller
            game.get_battlefield(self.controller).add(land)
            # Put remaining discarded cards into graveyard
            for c in discarded:
                if c is not land:
                    game.get_graveyard(target_player).add(c)
        else:
            # All discarded cards go to graveyard
            for c in discarded:
                game.get_graveyard(target_player).add(c)
