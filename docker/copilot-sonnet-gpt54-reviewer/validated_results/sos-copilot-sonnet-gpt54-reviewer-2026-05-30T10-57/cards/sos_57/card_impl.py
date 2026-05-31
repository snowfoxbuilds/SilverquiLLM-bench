"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return True if player controls at least one Wizard on the battlefield."""
    bf = game.get_battlefield(player)
    for card in bf.get_all():
        if "Wizard" in getattr(card, "subtypes", set()):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell at "
            "the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell and optionally schedule mana generation."""
        targets = getattr(self, "chosen_targets", None) or []
        if not targets:
            return

        stack_obj = targets[0]
        source_card = getattr(stack_obj, "source", None)

        # Counter the spell: remove from stack and move to owner's graveyard.
        if stack_obj in game.stack._items:
            game.stack._items.remove(stack_obj)

        if source_card is not None:
            owner = getattr(source_card, "owner", None)
            if owner is not None:
                owner.zones[Zone.GRAVEYARD].add(source_card)

        # If controller has a Wizard, schedule mana addition at next main phase.
        controller = self.controller
        if controller is not None and _controls_wizard(game, controller):
            # Calculate CMC of countered spell.
            spell_cost = getattr(source_card, "mana_cost", None) if source_card else None
            cmc = spell_cost.cmc if spell_cost is not None else 0
            if cmc > 0:
                self._register_mana_trigger(game, controller, cmc)

    def _register_mana_trigger(
        self, game: "GameState", controller: Any, amount: int
    ) -> None:
        """Register a one-shot trigger to add {C} at the start of next main phase."""
        source = self
        fired = [False]

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            if fired[0]:
                return False
            return getattr(event, "player", None) is controller

        def _effect(game: "GameState") -> None:
            fired[0] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
