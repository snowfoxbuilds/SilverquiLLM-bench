"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _is_spell_stack_object(game: "GameState", candidate: Any) -> bool:
    """Return True if *candidate* is a spell represented by a StackObject."""
    source = getattr(candidate, "source", None)
    if source is None:
        return False
    return any(player.zones[Zone.STACK].contains(source) for player in game.players)


def _controls_wizard(game: "GameState", player: "Player") -> bool:
    """Return True if *player* controls a Wizard on the battlefield."""
    battlefield = game.get_battlefield(player)
    return any("Wizard" in getattr(permanent, "subtypes", set()) for permanent in battlefield.get_all())


class ManaSculpt(Instant):
    """Mana Sculpt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} equal to "
            "the amount of mana spent to cast that spell at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        return any(_is_spell_stack_object(game, obj) for obj in game.stack.objects())

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda candidate: _is_spell_stack_object(game, candidate),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen_targets = getattr(self, "chosen_targets", []) or []
        target_obj = chosen_targets[0] if chosen_targets else None
        if not _is_spell_stack_object(game, target_obj):
            return

        target_spell = target_obj.source
        mana_spent = max(0, int(getattr(target_spell, "mana_spent_to_cast", 0)))

        game.stack.remove(target_obj)
        move_to_zone(game, target_spell, Zone.STACK, Zone.GRAVEYARD)

        controller = self.controller
        if controller is None or not _controls_wizard(game, controller) or mana_spent <= 0:
            return

        game.schedule_beginning_of_next_main_phase(
            controller,
            lambda g, controller=controller, mana_spent=mana_spent: controller.mana_pool.add(
                ManaType.COLORLESS,
                mana_spent,
            ),
        )
