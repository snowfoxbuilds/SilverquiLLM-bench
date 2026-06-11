"""Card implementation for Silverquill Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillCharm(Instant):
    """Silverquill Charm — {W}{B} — Instant.

    Choose one —
    • Put two +1/+1 counters on target creature.
    • Exile target creature with power 2 or less.
    • Each opponent loses 3 life and you gain 3 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
        kwargs.setdefault("rules_text",
            "Choose one —\n"
            "• Put two +1/+1 counters on target creature.\n"
            "• Exile target creature with power 2 or less.\n"
            "• Each opponent loses 3 life and you gain 3 life.")
        super().__init__(**kwargs)
        self.chosen_mode: int = 0
        self.chosen_targets: list[Any] = []

    def is_valid_target_for_mode(self, game: "GameState", mode: int, target: Any) -> bool:
        """Check if target is valid for a given mode."""
        if mode == 2:
            # Only creatures with power 2 or less
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return False
            return target.power <= 2
        return True

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the chosen mode."""
        mode = getattr(self, "chosen_mode", 0)
        targets = getattr(self, "chosen_targets", [])

        if mode == 1:
            # Put two +1/+1 counters on target creature
            if targets:
                target = targets[0]
                target.plus_one_counters += 2
                if hasattr(target, "_base_plus_one_counters"):
                    target._base_plus_one_counters = target.plus_one_counters

        elif mode == 2:
            # Exile target creature with power 2 or less
            if targets:
                target = targets[0]
                # Remove from battlefield and put in exile
                owner = getattr(target, "owner", None) or getattr(target, "controller", None)
                if owner is None:
                    owner = self.controller
                # Remove from any battlefield
                for player in game.players:
                    bf = game.get_battlefield(player)
                    if bf.contains(target):
                        bf.remove(target)
                        break
                game.get_exile(owner).add(target)

        elif mode == 3:
            # Each opponent loses 3 life and you gain 3 life
            controller = self.controller
            if controller is None:
                return
            for player in game.players:
                if player != controller:
                    player.life -= 3
            controller.life += 3
