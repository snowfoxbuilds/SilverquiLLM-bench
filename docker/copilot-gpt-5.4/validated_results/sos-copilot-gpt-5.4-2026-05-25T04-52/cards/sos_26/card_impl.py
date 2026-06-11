"""Card implementation for Primary Research."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Enchantment
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_small_nonland_permanent(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    if CardType.LAND in card_types:
        return False
    if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
        return False
    mana_cost = getattr(card, "mana_cost", None)
    return mana_cost is not None and mana_cost.cmc <= 3


class PrimaryResearch(Enchantment):
    """Primary Research."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Primary Research")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, return target nonland permanent card with mana "
            "value 3 or less from your graveyard to the battlefield.\nAt the beginning of "
            "your end step, if a card left your graveyard this turn, draw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        source = self

        def _filter(card: Any) -> bool:
            if not _is_small_nonland_permanent(card):
                return False
            current_controller = getattr(source, "controller", None)
            owner = getattr(card, "owner", None)
            return current_controller is None or owner is None or owner is current_controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent card with mana value 3 or less in your graveyard",
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

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            try:
                player_index = game.players.index(current_controller)
            except ValueError:
                return False
            return bool(game.cards_left_graveyards_this_turn.get(player_index))

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            draw_card(game, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
