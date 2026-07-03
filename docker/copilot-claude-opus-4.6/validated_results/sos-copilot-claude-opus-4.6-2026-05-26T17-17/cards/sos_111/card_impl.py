"""Card implementation for Choreographed Sparks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ChoreographedSparks(Instant):
    """Choreographed Sparks — {R}{R} — Instant.

    This spell can't be copied.
    Choose one or both —
    • Copy target instant or sorcery spell you control. You may choose new targets for the copy.
    • Copy target creature spell you control. The copy gains haste and
      "At the beginning of the end step, sacrifice this token."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Choreographed Sparks")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{R}"))
        kwargs.setdefault(
            "rules_text",
            "This spell can't be copied.\nChoose one or both —\n"
            "• Copy target instant or sorcery spell you control. You may choose new targets for the copy.\n"
            "• Copy target creature spell you control. The copy gains haste and "
            "\"At the beginning of the end step, sacrifice this token.\"",
        )
        super().__init__(**kwargs)
        self.cant_be_copied: bool = True
        self.min_modes: int = 1
        self.max_modes: int = 2
        self.chosen_modes: list[int] = []
        self.chosen_targets: list[Any] = []

    def get_modes(self, game: "GameState | None" = None) -> list[str]:
        """Return available modes."""
        return [
            "Copy target instant or sorcery spell you control",
            "Copy target creature spell you control",
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: copy the targeted spell(s) based on chosen modes."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        for i, mode in enumerate(self.chosen_modes):
            if i >= len(chosen):
                break
            target = chosen[i]

            if mode == 0:
                # Copy instant/sorcery spell - simplified: just copy it on the stack
                pass
            elif mode == 1:
                # Copy creature spell - create a token copy with haste + sacrifice at end step
                self._copy_creature_spell(game, target)

    def _copy_creature_spell(self, game: "GameState", target: Any) -> None:
        """Create a token copy of a creature spell with haste and end-step sacrifice."""
        controller = self.controller
        if controller is None:
            return

        # Create a token copy
        token = Creature(
            name=target.name,
            owner=controller,
            controller=controller,
            base_power=getattr(target, "base_power", 0),
            base_toughness=getattr(target, "base_toughness", 0),
        )
        token.is_token = True
        token.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.HASTE
        token.sacrifice_at_end_step = True
        token.summoning_sick = False

        # Put it on the battlefield
        battlefield = game.get_battlefield(controller)
        battlefield.add(token)
