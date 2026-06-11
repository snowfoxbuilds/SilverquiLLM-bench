"""Card implementation for Pull from the Grave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PullFromTheGrave(Sorcery):
    """Pull from the Grave."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pull from the Grave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return up to two target creature cards from your graveyard to your hand. "
            "You gain 2 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        requirement = TargetRequirement(
            filter_fn=lambda obj, _controller=controller: (
                isinstance(obj, Creature) and getattr(obj, "owner", None) is _controller
            ),
            description="creature card in your graveyard",
            zone=Zone.GRAVEYARD,
        )
        requirement.min_targets = 0  # type: ignore[attr-defined]
        requirement.max_targets = 2  # type: ignore[attr-defined]
        requirement.distinct_targets = True  # type: ignore[attr-defined]
        return [requirement]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        legal_target_found = False
        seen: set[int] = set()
        chosen_targets = getattr(self, "chosen_targets", [])
        for target in chosen_targets[:2]:
            if not isinstance(target, Creature):
                continue
            if id(target) in seen:
                continue
            seen.add(id(target))
            if getattr(target, "owner", None) is controller and graveyard.contains(target):
                legal_target_found = True
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)

        if chosen_targets and not legal_target_found:
            return

        controller.life += 2
        controller.life_gained_this_turn = getattr(controller, "life_gained_this_turn", 0) + 2
        game.trigger_manager.fire_event(
            game,
            GainsLifeTriggeredEvent(player=controller, amount=2),
        )
