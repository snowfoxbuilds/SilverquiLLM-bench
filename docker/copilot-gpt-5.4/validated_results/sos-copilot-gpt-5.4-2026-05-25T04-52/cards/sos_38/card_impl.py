"""Card implementation for Banishing Betrayal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


_NONLAND_PERMANENT_TYPES = {
    CardType.CREATURE,
    CardType.ARTIFACT,
    CardType.ENCHANTMENT,
    CardType.PLANESWALKER,
}


class BanishingBetrayal(Instant):
    """Banishing Betrayal."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banishing Betrayal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return target nonland permanent to its owner's hand. Surveil 1.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: bool(
                    getattr(obj, "card_types", set()) & _NONLAND_PERMANENT_TYPES
                ) and CardType.LAND not in getattr(obj, "card_types", set()),
                description="target nonland permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if target is not None and any(
            game.get_battlefield(player).contains(target)
            for player in game.players
        ):
            if (
                getattr(target, "card_types", set()) & _NONLAND_PERMANENT_TYPES
                and CardType.LAND not in getattr(target, "card_types", set())
            ):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        if len(library) == 0:
            return
        top_card = library.top(1)[0]
        if controller.choose_yes_no("Put the top card of your library into your graveyard?"):
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)
