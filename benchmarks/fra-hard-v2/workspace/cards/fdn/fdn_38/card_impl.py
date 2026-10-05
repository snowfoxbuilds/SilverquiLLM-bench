"""Card implementation for Faebloom Trick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.tokens import make_creature_token
from engine.card import Instant
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class FaebloomTrickAbility1:
    text = 'Create two 1/1 blue Faerie creature tokens with flying. When you do, tap target creature an opponent controls.'


# endregion Printed abilities


class FaebloomTrick(Instant):
    """Faebloom Trick — {2}{U} — Instant.

    Create two 1/1 blue Faerie creature tokens with flying. When you do,
    tap target creature an opponent controls.

    FDN collector number 38.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Faebloom Trick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 1/1 blue Faerie creature tokens with flying. "
            "When you do, tap target creature an opponent controls.",
        )
        super().__init__(**kwargs)

    def _is_opponent_creature(self, obj: Any) -> bool:
        """Legal target: a creature controlled by a player other than me."""
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            return False
        obj_controller = getattr(obj, "controller", None)
        return obj_controller is not None and obj_controller is not self.controller

    def on_resolve(self, game: "GameState") -> None:
        """Create two Faerie tokens, then tap the chosen opponent creature."""
        from engine.game import create_token
        from engine.triggers import put_reflexive_trigger

        controller = self.controller
        if controller is None:
            return

        # Create two 1/1 blue Faerie tokens with flying.
        for _ in range(2):
            token = make_creature_token(
                "Faerie",
                {"Faerie"},
                [Color.BLUE],
                1,
                1,
                keywords=Keyword.FLYING,
            )
            create_token(game, controller, token)

        # "When you do" is a reflexive trigger: it targets as it goes on the
        # stack, after the tokens are made.
        put_reflexive_trigger(
            game, self, controller, FaebloomTrickAbility1, self._tap_target,
            targets=[TargetRequirement(
                filter_fn=self._is_opponent_creature,
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            )],
        )

    def _tap_target(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Tap the target, if it is still a creature an opponent controls."""
        from engine.game import tap

        target = targets[0] if targets else None
        if target is not None and self._is_opponent_creature(target):
            tap(game, target)
