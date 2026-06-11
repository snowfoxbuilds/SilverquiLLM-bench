"""Card implementation for Restoration Seminar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_nonland_permanent(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    if CardType.LAND in card_types:
        return False
    return bool(card_types & {CardType.CREATURE, CardType.ENCHANTMENT, CardType.ARTIFACT, CardType.PLANESWALKER})


class RestorationSeminar(Sorcery):
    """Restoration Seminar."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Restoration Seminar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{W}{W}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self.paradigm_enabled = True

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        source = self

        def _filter(card: Any) -> bool:
            if not _is_nonland_permanent(card):
                return False
            current_controller = getattr(source, "controller", None)
            owner = getattr(card, "owner", None)
            return current_controller is None or owner is None or owner is current_controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
        controller = self.controller
        if target is None or controller is None:
            return
        if not game.get_graveyard(controller).contains(target):
            return
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
