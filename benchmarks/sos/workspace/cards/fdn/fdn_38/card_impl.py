"""Card implementation for Faebloom Trick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


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

    def get_targets(self, game: "GameState") -> list:
        """Choose target creature an opponent controls to tap."""
        controller = self.controller
        if controller is None:
            return []
        targets: list = []
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                from benchmarks.sos.workspace.engine.types import CardType
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE in card_types:
                    targets.append(obj)
        if not targets:
            return []
        chosen = controller.choose_target(targets, "creature an opponent controls") if hasattr(controller, "choose_target") else targets[0]
        return [chosen] if chosen else []

    def on_resolve(self, game: "GameState") -> None:
        """Create two Faerie tokens, then tap target opponent creature."""
        from benchmarks.sos.workspace.engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Create two 1/1 blue Faerie tokens with flying
        for _ in range(2):
            token = Creature(
                name="Faerie",
                subtypes={"Faerie"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(game, controller, token)

        # Reflexive trigger: tap target creature an opponent controls
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else getattr(self, "_resolve_target", None)
        if target is not None:
            # Verify target is still on opponent's battlefield
            for player in game.players:
                if player is controller:
                    continue
                bf = game.get_battlefield(player)
                if bf.contains(target):
                    target.is_tapped = True
                    target.tapped = True
                    break
