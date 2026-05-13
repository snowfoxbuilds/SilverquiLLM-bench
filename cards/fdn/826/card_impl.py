"""Card implementation for DromokasCommand."""

from __future__ import annotations


from engine.card import Instant, Mode, Sorcery
from engine.types import CardType, ManaCost
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _get_targets(card: Any) -> list[Any]:
    """Return chosen targets list."""
    return getattr(card, "chosen_targets", []) or []


class DromokasCommand(Sorcery):
    """Dromoka's Command — {G}{W} — Choose two.

    - Put a +1/+1 counter on target creature.
    - Target creature you control fights target creature you don't control.
    - Target player sacrifices an enchantment.
    - Prevent all damage target instant or sorcery spell would deal this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dromoka's Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Put a +1/+1 counter on target creature.\n"
            "• Target creature you control fights target creature you don't control.\n"
            "• Target player sacrifices an enchantment.\n"
            "• Prevent all damage target instant or sorcery spell would deal this turn.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Counter", description="Put a +1/+1 counter on target creature."),
            Mode(name="Fight", description="Target creature you control fights target creature you don't control."),
            Mode(name="Sacrifice Enchantment", description="Target player sacrifices an enchantment."),
            Mode(name="Prevent Damage", description="Prevent all damage target instant or sorcery spell would deal this turn."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Put a +1/+1 counter on target creature.
                target = _get_target(self)
                if target is not None and hasattr(target, "plus_one_counters"):
                    target.plus_one_counters += 1
                    target._original_plus_one_counters = target.plus_one_counters
            elif mode == 1:
                # Fight — target creature you control fights target creature
                # you don't control (simplified: deal damage to each other).
                targets = _get_targets(self)
                if len(targets) >= 2:
                    from engine.game import deal_damage
                    a, b = targets[0], targets[1]
                    deal_damage(game, a, b, getattr(a, "power", 0))
                    deal_damage(game, b, a, getattr(b, "power", 0))
            elif mode == 2:
                # Target player sacrifices an enchantment.
                from engine.game import sacrifice
                target = _get_target(self)
                if target is not None:
                    bf = game.get_battlefield(target) if hasattr(target, "zones") else None
                    if bf is not None:
                        for obj in bf.get_all():
                            if CardType.ENCHANTMENT in getattr(obj, "card_types", set()):
                                sacrifice(game, target, obj)
                                break
            elif mode == 3:
                # Prevent damage — simplified stub.
                pass


__all__ = ["DromokasCommand"]
