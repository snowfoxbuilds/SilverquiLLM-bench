"""Card implementation for Quandrix Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Mode
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class QuandrixCharm(Instant):
    """Quandrix Charm — {G}{U} — Instant.

    Choose one —
    • Counter target spell unless its controller pays {2}.
    • Destroy target enchantment.
    • Target creature has base power and toughness 5/5 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quandrix Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Counter target spell unless its controller pays {2}.\n"
            "• Destroy target enchantment.\n"
            "• Target creature has base power and toughness 5/5 until end of turn.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int = 0
        self.chosen_targets: list[Any] = []

    def get_modes(self, game: "GameState" = None) -> list[Mode]:
        """Return the three modes."""
        return [
            Mode(name="Counter spell", description="Counter target spell unless its controller pays {2}."),
            Mode(name="Destroy enchantment", description="Destroy target enchantment."),
            Mode(name="Pump creature", description="Target creature has base power and toughness 5/5 until end of turn."),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the chosen mode."""
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        if self.chosen_mode == 0:
            # Counter target spell unless its controller pays {2}
            target_spell = targets[0]
            # For simplicity, assume they don't pay
            # Move the spell to graveyard (counter it)
            owner = getattr(target_spell, "owner", None)
            if owner is not None:
                # Remove from stack if on stack
                if hasattr(game, "stack"):
                    game.stack._items = [
                        item for item in game.stack._items
                        if getattr(item, "source", None) is not target_spell
                    ]
                # Remove from stack zone
                stack_zone = owner.zones[Zone.STACK] if hasattr(owner, "zones") else None
                if stack_zone and stack_zone.contains(target_spell):
                    stack_zone.remove(target_spell)
                # Move to graveyard
                target_spell.zone = Zone.GRAVEYARD
                game.get_graveyard(owner).add(target_spell)

        elif self.chosen_mode == 1:
            # Destroy target enchantment
            target_ench = targets[0]
            owner = getattr(target_ench, "owner", None) or getattr(target_ench, "controller", None)
            # Remove from battlefield
            for player in game.players:
                bf = game.get_battlefield(player)
                if bf.contains(target_ench):
                    bf.remove(target_ench)
                    break
            # Move to graveyard
            target_ench.zone = Zone.GRAVEYARD
            if owner:
                game.get_graveyard(owner).add(target_ench)

        elif self.chosen_mode == 2:
            # Target creature has base P/T 5/5 until end of turn
            target_creature = targets[0]
            original_power = target_creature.base_power
            original_toughness = target_creature.base_toughness
            target_creature.base_power = 5
            target_creature.base_toughness = 5

            # Register end-of-turn cleanup
            if not hasattr(game, "_eot_cleanup_callbacks"):
                game._eot_cleanup_callbacks = []
            game._eot_cleanup_callbacks.append(
                lambda c=target_creature, op=original_power, ot=original_toughness: (
                    setattr(c, "base_power", op),
                    setattr(c, "base_toughness", ot),
                )
            )
