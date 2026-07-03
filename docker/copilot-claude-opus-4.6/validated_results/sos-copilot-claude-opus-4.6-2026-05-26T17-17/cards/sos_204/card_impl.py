"""Card implementation for Molten Note."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MoltenNote(Sorcery):
    """Molten Note — {X}{R}{W} — Sorcery.

    Molten Note deals damage to target creature equal to the amount of mana
    spent to cast this spell. Untap all creatures you control.
    Flashback {6}{R}{W}
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Molten Note")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{R}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        super().__init__(**kwargs)
        self.flashback_cost: ManaCost = ManaCost.parse("{6}{R}{W}")
        self.x_value: int = 0
        self.mana_spent: int = 0
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Requires a creature target."""
        return [TargetRequirement(
            filter_fn=lambda obj: CardType.CREATURE in getattr(obj, 'card_types', set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """Deal damage equal to mana spent to target creature. Untap your creatures."""
        if self.controller is None:
            return

        # Deal damage to target creature
        if self.chosen_targets:
            target = self.chosen_targets[0]
            damage = self.mana_spent
            target.damage_marked = getattr(target, 'damage_marked', 0) + damage

        # Untap all creatures you control
        bf = game.get_battlefield(self.controller)
        for perm in bf.get_all():
            if CardType.CREATURE in getattr(perm, 'card_types', set()):
                perm.is_tapped = False
