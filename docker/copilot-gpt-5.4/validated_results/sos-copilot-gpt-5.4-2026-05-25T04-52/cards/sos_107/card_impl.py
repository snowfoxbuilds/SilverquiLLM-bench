"""Card implementation for Archaic's Agony."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArchaicsAgony(Sorcery):
    """Archaic's Agony."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Archaic's Agony")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Archaic's Agony deals X damage to target creature, where X is the number "
            "of colors of mana spent to cast this spell. Exile cards from the top of your library "
            "equal to the excess damage dealt to that creature this way. You may play those cards "
            "until the end of your next turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        target = getattr(self, "chosen_targets", [None])[0]
        colors_spent = getattr(self, "colors_spent", [])
        distinct_color_count = len({color for color in colors_spent if isinstance(color, Color)})

        if controller is None or not isinstance(target, Creature) or not target.is_on_battlefield(game):
            return
        if distinct_color_count <= 0:
            return

        remaining_toughness = max(0, target.toughness - target.damage_marked)
        deal_damage(game, self, target, distinct_color_count)

        excess_damage = max(0, distinct_color_count - remaining_toughness)
        if excess_damage <= 0:
            return

        library = game.get_library(controller)
        for card in reversed(library.top(excess_damage)):
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            game.grant_exile_play_permission_until_end_of_next_turn(
                controller,
                card,
                source=self,
            )
