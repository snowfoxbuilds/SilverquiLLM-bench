"""Card implementation for Archaic's Agony."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ArchaicsAgony(Sorcery):
    """Archaic's Agony — {4}{R} — Sorcery.

    Converge — Archaic's Agony deals X damage to target creature, where X is
    the number of colors of mana spent to cast this spell. Exile cards from
    the top of your library equal to the excess damage dealt to that creature
    this way. You may play those cards until the end of your next turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Archaic's Agony")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)
        self.colors_spent: int = 0

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        controller = self.controller or self.owner
        damage = self.colors_spent

        # Deal damage
        from engine.game import deal_damage
        deal_damage(game, self, target, damage)

        # Calculate excess damage: damage dealt minus toughness
        toughness = getattr(target, "toughness", 0)
        excess = max(0, damage - toughness)

        if excess > 0:
            # Exile cards from top of library
            library = game.get_library(controller)
            exile_zone = game.get_exile(controller)
            for _ in range(excess):
                if len(library) == 0:
                    break
                cards = library.top(1)
                card = cards[0]
                library.remove(card)
                exile_zone.add(card)
