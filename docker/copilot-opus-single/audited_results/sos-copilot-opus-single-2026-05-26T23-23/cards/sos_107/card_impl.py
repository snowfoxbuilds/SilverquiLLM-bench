"""Card implementation for Archaic's Agony."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ArchaicsAgony(Sorcery):
    """Archaic's Agony — {4}{R} — Sorcery.

    Converge — Archaic's Agony deals X damage to target creature, where X is
    the number of colors of mana spent to cast this spell. Exile cards from the
    top of your library equal to the excess damage dealt to that creature this
    way. You may play those cards until the end of your next turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Archaic's Agony")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Archaic's Agony deals X damage to target creature, "
            "where X is the number of colors of mana spent to cast this spell. "
            "Exile cards from the top of your library equal to the excess damage "
            "dealt to that creature this way. You may play those cards until the "
            "end of your next turn.",
        )
        super().__init__(**kwargs)
        self.colors_spent: int = 0
        self.targets: list[Any] = []

    def on_resolve(self, game: GameState) -> None:
        """Resolve Archaic's Agony: deal converge damage, exile excess cards."""
        if not self.targets:
            return

        target = self.targets[0]
        damage = self.colors_spent

        if damage <= 0:
            return

        # Calculate remaining toughness before dealing damage
        remaining_toughness = target.base_toughness - getattr(target, "damage_marked", 0)

        # Deal the damage
        target.damage_marked = getattr(target, "damage_marked", 0) + damage

        # Calculate excess damage (damage beyond what's needed to be lethal)
        excess = max(0, damage - remaining_toughness)

        if excess <= 0:
            return

        # Exile cards from top of controller's library equal to excess
        controller = getattr(self, "controller", None) or self.owner
        library = game.get_library(controller)
        exile_zone = game.get_exile(controller)

        lib_cards = library.get_all()
        # Top cards are at the end of the list
        cards_to_exile = min(excess, len(lib_cards))

        for _ in range(cards_to_exile):
            # Get current top card (last in list)
            current = library.get_all()
            if not current:
                break
            top_card = current[-1]
            library.remove(top_card)
            # Mark as playable (impulse draw)
            top_card.playable_by = controller
            top_card.impulse_draw = True
            top_card.may_be_played_by = controller
            exile_zone.add(top_card)
