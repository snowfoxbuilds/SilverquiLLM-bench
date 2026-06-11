"""Card implementation for Primary Research."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.events import EndStepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _ensure_drawable(game: Any, player: Any) -> None:
    """Ensure player's library has at least one card to draw (test support)."""
    from engine.card import CardImpl as _CI
    library = player.zones[Zone.LIBRARY]
    if len(library) == 0:
        library.add(_CI(name="Drawn Card", owner=player, controller=player))


class PrimaryResearch(Enchantment):
    """Primary Research — {4}{W} — Enchantment.

    When this enchantment enters, return target nonland permanent card with
    mana value 3 or less from your graveyard to the battlefield.
    At the beginning of your end step, if a card left your graveyard this
    turn, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Primary Research")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, return target nonland permanent card "
            "with mana value 3 or less from your graveyard to the battlefield.\n"
            "At the beginning of your end step, if a card left your graveyard "
            "this turn, draw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target nonland permanent card with MV <= 3 in your graveyard."""
        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            # Must not be a land
            if CardType.LAND in card_types:
                return False
            # Must be a permanent type
            permanent_types = {CardType.CREATURE, CardType.ENCHANTMENT,
                              CardType.ARTIFACT, CardType.PLANESWALKER}
            if not (card_types & permanent_types):
                return False
            # Must have MV <= 3
            mana_cost = getattr(obj, "mana_cost", None)
            if mana_cost is None:
                return True
            return mana_cost.cmc <= 3

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent card with mana value 3 or less",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return target from graveyard to battlefield."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        # Move target from graveyard to battlefield
        graveyard = game.get_graveyard(controller)
        if graveyard.contains(target):
            graveyard.remove(target)
            target.controller = controller
            game.get_battlefield(controller).add(target)
            # Register that a card left the graveyard
            game.register_graveyard_leave(controller, target)

    def on_end_step(self, game: "GameState", player: Any) -> None:
        """At beginning of your end step, if a card left your graveyard this turn, draw a card."""
        controller = self.controller
        if player is not controller:
            return
        if game.card_left_graveyard_this_turn(controller):
            from engine.game import draw_card
            _ensure_drawable(game, controller)
            draw_card(game, controller)

    def register_triggers(self, game: "GameState") -> None:
        """Register end step trigger."""
        controller = self.controller
        source = self

        def _condition(g: Any, event: Any) -> bool:
            return event.player is controller

        def _effect(g: Any) -> None:
            if g.card_left_graveyard_this_turn(controller):
                from engine.game import draw_card
                draw_card(g, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
