"""Card implementation for AustereCommand."""

from __future__ import annotations


from engine.card import Instant, Mode, Sorcery
from engine.types import CardType, ManaCost
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class AustereCommand(Sorcery):
    """Austere Command — {4}{W}{W} — Choose two.

    - Destroy all artifacts.
    - Destroy all enchantments.
    - Destroy all creatures with mana value 3 or less.
    - Destroy all creatures with mana value 4 or greater.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Austere Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Destroy all artifacts.\n"
            "• Destroy all enchantments.\n"
            "• Destroy all creatures with mana value 3 or less.\n"
            "• Destroy all creatures with mana value 4 or greater.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Artifacts", description="Destroy all artifacts."),
            Mode(name="Enchantments", description="Destroy all enchantments."),
            Mode(name="Small Creatures", description="Destroy all creatures with mana value 3 or less."),
            Mode(name="Large Creatures", description="Destroy all creatures with mana value 4 or greater."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        from engine.game import destroy
        to_destroy: list[Any] = []
        for mode in modes:
            for player in game.players:
                for obj in game.get_battlefield(player).get_all():
                    if mode == 0 and CardType.ARTIFACT in getattr(obj, "card_types", set()):
                        to_destroy.append(obj)
                    elif mode == 1 and CardType.ENCHANTMENT in getattr(obj, "card_types", set()):
                        to_destroy.append(obj)
                    elif mode == 2 and CardType.CREATURE in getattr(obj, "card_types", set()):
                        cmc = getattr(obj, "mana_value", 0)
                        if cmc is None:
                            cmc = getattr(obj.mana_cost, "mana_value", 0) if obj.mana_cost else 0
                        if cmc <= 3:
                            to_destroy.append(obj)
                    elif mode == 3 and CardType.CREATURE in getattr(obj, "card_types", set()):
                        cmc = getattr(obj, "mana_value", 0)
                        if cmc is None:
                            cmc = getattr(obj.mana_cost, "mana_value", 0) if obj.mana_cost else 0
                        if cmc >= 4:
                            to_destroy.append(obj)
        for obj in to_destroy:
            if _is_on_battlefield(game, obj):
                destroy(game, obj)


__all__ = ["AustereCommand"]
