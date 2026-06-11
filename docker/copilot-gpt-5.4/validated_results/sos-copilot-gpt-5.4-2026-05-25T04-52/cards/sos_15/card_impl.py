"""Card implementation for Erode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant, Planeswalker
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Erode(Instant):
    """Erode."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Erode")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target creature or planeswalker. Its controller may search their library for a "
            "basic land card, put it onto the battlefield tapped, then shuffle.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, (Creature, Planeswalker)),
                description="target creature or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, (Creature, Planeswalker)):
            return

        target_controller = getattr(target, "controller", None)
        if target_controller is None or not game.get_battlefield(target_controller).contains(target):
            return

        destroy(game, target)
        if not game.get_graveyard(getattr(target, "owner", target_controller)).contains(target):
            return

        try:
            should_search = target_controller.choose_yes_no(
                "Search your library for a basic land card?"
            )
        except Exception:
            should_search = False
        if not should_search:
            return

        library = game.get_library(target_controller)
        candidates = [
            card for card in library.get_all() if Supertype.BASIC in getattr(card, "supertypes", set())
        ]
        if not candidates:
            library.shuffle()
            return

        try:
            chosen = target_controller.choose_card(candidates, "Choose a basic land card")
        except Exception:
            chosen = candidates[0]

        if chosen is None or not library.contains(chosen):
            library.shuffle()
            return

        chosen.controller = target_controller
        move_to_zone(game, chosen, Zone.LIBRARY, Zone.BATTLEFIELD)
        chosen.is_tapped = True
        library.shuffle()
