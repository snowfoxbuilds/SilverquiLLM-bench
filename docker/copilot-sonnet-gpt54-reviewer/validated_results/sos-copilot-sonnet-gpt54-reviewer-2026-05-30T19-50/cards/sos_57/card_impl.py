"""Card implementation for Mana Sculpt (SOS #57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant (Rare).

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell; conditionally schedule colorless mana."""
        controller = self.controller
        if controller is None:
            return

        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        target_so = targets[0]
        target_card = getattr(target_so, "source", target_so)

        # Determine mana value of the spell before countering it.
        mana_value = 0
        mc = getattr(target_card, "mana_cost", None)
        if mc is not None:
            mana_value = mc.cmc

        # Counter the spell: remove from stack and move card to owner's graveyard.
        if target_so in game.stack._items:
            game.stack._items.remove(target_so)
        owner = getattr(target_card, "owner", None) or getattr(
            target_so, "controller", controller
        )
        if owner is not None:
            game.get_graveyard(owner).add(target_card)

        # Condition: controller must control a Wizard.
        if not _controls_wizard(game, controller) or mana_value <= 0:
            return

        # Register a one-shot delayed trigger for beginning of next main phase.
        _register_mana_trigger(game, controller, mana_value)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return True if *player* controls at least one Wizard on the battlefield."""
    bf = game.get_battlefield(player)
    for obj in bf.get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            if "Wizard" in getattr(obj, "subtypes", set()):
                return True
    return False


def _register_mana_trigger(
    game: "GameState", controller: Any, mana_value: int
) -> None:
    """Register a one-shot trigger to add *mana_value* {C} at next main phase."""
    from engine.events import BeginningOfMainPhaseTriggeredEvent
    from engine.triggers import TriggerRegistration

    # Use a list as a mutable sentinel so _effect can reference the registration.
    sentinel: list[Any] = []

    def _condition(game: Any, event: Any) -> bool:
        return game.active_player is controller

    def _effect(game: Any) -> None:
        # Remove this one-shot trigger immediately before adding mana.
        game.trigger_manager.unregister(sentinel)
        controller.mana_pool.add(ManaType.COLORLESS, mana_value)

    reg = TriggerRegistration(
        event_type=BeginningOfMainPhaseTriggeredEvent,
        condition=_condition,
        effect=_effect,
        source=sentinel,
        controller=controller,
    )
    sentinel.append(reg)
    game.trigger_manager.register(reg)
