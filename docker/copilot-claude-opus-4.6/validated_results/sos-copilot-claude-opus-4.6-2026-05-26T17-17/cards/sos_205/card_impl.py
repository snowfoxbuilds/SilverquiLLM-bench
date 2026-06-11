"""Card implementation for Moment of Reckoning."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Mode, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MomentOfReckoning(Sorcery):
    """Moment of Reckoning — {3}{W}{W}{B}{B} — Sorcery.

    Choose up to four. You may choose the same mode more than once.
    • Destroy target nonland permanent.
    • Return target nonland permanent card from your graveyard to the battlefield.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Moment of Reckoning")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}{B}{B}"))
        super().__init__(**kwargs)
        self.modes: list[Mode] = [
            Mode(name="Destroy target nonland permanent.",
                 description="Destroy target nonland permanent."),
            Mode(name="Return target nonland permanent card from your graveyard to the battlefield.",
                 description="Return target nonland permanent card from your graveyard to the battlefield."),
        ]
        self.max_modes: int = 4
        self.repeatable_modes: bool = True
        self.chosen_modes: list[int] = []
        self.chosen_targets: list[Any] = []

    def get_modes(self) -> list[Mode]:
        """Return available modes."""
        return self.modes

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return target requirements for both modes."""
        def _is_nonland_permanent(obj: Any) -> bool:
            card_types = getattr(obj, 'card_types', set())
            return bool(card_types) and CardType.LAND not in card_types

        def _is_nonland_permanent_in_gy(obj: Any) -> bool:
            card_types = getattr(obj, 'card_types', set())
            if not card_types or CardType.LAND in card_types:
                return False
            # Must not be instant/sorcery (not permanents)
            if card_types <= {CardType.INSTANT, CardType.SORCERY}:
                return False
            return True

        return [
            TargetRequirement(
                filter_fn=_is_nonland_permanent,
                description="target nonland permanent",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_is_nonland_permanent_in_gy,
                description="target nonland permanent card in your graveyard",
                zone=Zone.GRAVEYARD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Execute chosen modes with corresponding targets."""
        if self.controller is None:
            return

        for i, mode_index in enumerate(self.chosen_modes):
            if i >= len(self.chosen_targets):
                break
            target = self.chosen_targets[i]

            if mode_index == 0:
                # Destroy target nonland permanent
                owner = getattr(target, 'controller', None) or getattr(target, 'owner', None)
                if owner is not None:
                    bf = game.get_battlefield(owner)
                    if target in bf.get_all():
                        bf.remove(target)
                        game.get_graveyard(owner).add(target)
            elif mode_index == 1:
                # Return target nonland permanent from graveyard to battlefield
                owner = getattr(target, 'owner', None) or self.controller
                gy = game.get_graveyard(self.controller)
                if target in gy.get_all():
                    gy.remove(target)
                    target.controller = self.controller
                    game.get_battlefield(self.controller).add(target)
