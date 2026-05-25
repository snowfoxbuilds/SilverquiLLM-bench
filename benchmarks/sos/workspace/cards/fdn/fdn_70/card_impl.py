"""Card implementation for Soul-Shackled Zombie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SoulShackledZombie(Creature):
    """Soul-Shackled Zombie — {3}{B} — 4/2 — Zombie.

    When this creature enters, exile up to two target cards from a single
    graveyard. If at least one creature card was exiled this way, each
    opponent loses 2 life and you gain 2 life.

    FDN collector number 70.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soul-Shackled Zombie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, exile up to two target cards from a "
            "single graveyard. If at least one creature card was exiled this "
            "way, each opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: exile up to two cards from a single graveyard."""
        from engine.game import exile

        controller = self.controller
        if controller is None:
            return

        # Find all cards in all graveyards
        # Let controller choose cards from a single graveyard
        all_gy_cards: list = []
        for player in game.players:
            gy = player.zones[Zone.GRAVEYARD]
            cards = gy.get_all()
            if cards:
                all_gy_cards.extend(cards)

        if not all_gy_cards:
            return

        exiled_creature = False
        exiled_count = 0

        # Choose up to two from a single graveyard
        try:
            first = controller.choose_card(all_gy_cards, "card to exile from graveyard")
        except Exception:
            first = all_gy_cards[0] if all_gy_cards else None

        if first is None:
            return

        if CardType.CREATURE in getattr(first, "card_types", set()):
            exiled_creature = True
        exile(game, first)
        exiled_count += 1

        # Find remaining cards from the same graveyard
        owner = getattr(first, "owner", None)
        if owner is not None and exiled_count < 2:
            gy = owner.zones[Zone.GRAVEYARD]
            remaining = gy.get_all()
            if remaining:
                try:
                    second = controller.choose_card(remaining, "second card to exile")
                except Exception:
                    second = None
                if second is not None:
                    if CardType.CREATURE in getattr(second, "card_types", set()):
                        exiled_creature = True
                    exile(game, second)

        # If at least one creature was exiled, drain
        if exiled_creature:
            for player in game.players:
                if player is not controller:
                    player.life -= 2
            controller.life += 2
