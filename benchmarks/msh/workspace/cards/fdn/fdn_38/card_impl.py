"""Card implementation for Faebloom Trick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Up-to-one target creature an opponent controls (the reflexive tap).

        The reflexive "when you do, tap target creature an opponent controls"
        only puts a target on the stack if a legal one exists, and the token
        creation always happens — so the tap is modelled as an optional
        ("up to one") requirement: the spell stays castable (and still makes
        tokens) even with no opponent creatures.
        """
        return [
            TargetRequirement(
                filter_fn=self._is_opponent_creature,
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
                optional=True,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Create two Faerie tokens, then tap the chosen opponent creature."""
        from engine.game import create_token, tap

        controller = self.controller
        if controller is None:
            return

        # Create two 1/1 blue Faerie tokens with flying.
        for _ in range(2):
            token = Creature(
                name="Faerie",
                subtypes={"Faerie"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(game, controller, token)

        # Reflexive trigger: tap the chosen creature an opponent controls.
        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return
        for player in game.players:
            if player is controller:
                continue
            if game.get_battlefield(player).contains(target):
                tap(game, target)
                return
