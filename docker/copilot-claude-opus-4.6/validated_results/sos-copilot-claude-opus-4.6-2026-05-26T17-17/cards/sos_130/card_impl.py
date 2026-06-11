"""Card implementation for Steal the Show."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.game import draw_card, discard
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StealTheShow(Sorcery):
    """Steal the Show — {2}{R} — Sorcery.

    Choose one or both:
    - Target player discards any number of cards, then draws that many.
    - Deals damage equal to instant/sorcery cards in your graveyard to
      target creature or planeswalker.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Steal the Show")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
        self.chosen_modes: list[int] = []
        self.chosen_targets: list[Any] = []
        self.discard_count: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Resolve based on chosen modes."""
        player = self.controller

        if 1 in self.chosen_modes:
            # Mode 1: target player discards any number, then draws that many
            target_player = self.chosen_targets[0] if self.chosen_targets else player
            count = self.discard_count
            if count > 0:
                hand = game.get_hand(target_player)
                cards_to_discard = hand.get_all()[:count]
                for card in cards_to_discard:
                    discard(game, target_player, card)
                for _ in range(count):
                    draw_card(game, target_player)

        if 2 in self.chosen_modes:
            # Mode 2: deal damage equal to instant/sorcery count in caster's graveyard
            target_idx = 1 if (1 in self.chosen_modes and len(self.chosen_targets) > 1) else 0
            target = self.chosen_targets[target_idx] if len(self.chosen_targets) > target_idx else None
            if target is None:
                return
            # Count instants and sorceries in controller's graveyard
            graveyard = game.get_graveyard(player)
            count = 0
            for card in graveyard:
                card_types = getattr(card, 'card_types', set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    count += 1
            # Deal damage
            if hasattr(target, 'damage_marked'):
                target.damage_marked += count
            elif hasattr(target, 'life'):
                target.life -= count
