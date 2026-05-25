"""Card implementation for Self-Reflection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SelfReflection(Sorcery):
    """Self-Reflection — {4}{U}{U} — Sorcery.

    Create a token that's a copy of target creature you control.
    Flashback {3}{U}

    FDN collector number 163.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Self-Reflection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a token that's a copy of target creature you control.\n"
            "Flashback {3}{U}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{3}{U}")

    def get_targets(self, game: "GameState") -> list:
        """Target creature you control."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is getattr(self, "controller", None)
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Create a token copy of target creature you control."""
        import copy

        from benchmarks.sos.workspace.engine.game import create_token

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        controller = self.controller
        if controller is None:
            return
        # Create token copy
        token = copy.copy(target)
        token.is_token = True
        create_token(game, controller, token)
