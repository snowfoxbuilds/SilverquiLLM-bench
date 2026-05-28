"""Card implementation for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the mana value of the countered spell at the beginning of
    your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the mana value of the countered spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return a single targeting requirement: a spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell. If we control a Wizard, register
        a delayed trigger to add {C} equal to the countered spell's CMC
        at the beginning of our next main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        chosen_targets = getattr(self, "chosen_targets", [])
        if not chosen_targets:
            return

        target = chosen_targets[0]

        # Determine the mana value of the countered spell before removing it.
        source_card = getattr(target, "source", None)
        if source_card is not None:
            mana_cost = getattr(source_card, "mana_cost", None)
        else:
            mana_cost = None
        countered_cmc: int = mana_cost.cmc if mana_cost is not None else 0

        # Remove the target from the stack (counter it).
        game.stack._items = [
            item for item in game.stack._items if item is not target
        ]

        # Check if the controller controls a Wizard.
        controller = self.controller
        if controller is None:
            return

        has_wizard = self._controller_has_wizard(game, controller)
        if not has_wizard:
            return

        # Register a one-shot delayed trigger for the beginning of the
        # controller's next main phase.
        source = self
        cmc_to_add = countered_cmc

        def _delayed_mana_effect(g: "GameState") -> None:
            if cmc_to_add > 0:
                controller.mana_pool.add(ManaType.COLORLESS, cmc_to_add)
            # Unregister this one-shot trigger after it fires.
            g.trigger_manager.unregister(source)

        def _condition(g: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            # Fire only for the controller's main phase.
            return event.active_player is controller

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_delayed_mana_effect,
                source=source,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _controller_has_wizard(game: "GameState", controller: Any) -> bool:
        """Return True if the controller has a Wizard on the battlefield."""
        bf = game.get_battlefield(controller)
        for permanent in bf.get_all():
            subtypes = getattr(permanent, "subtypes", set())
            if "Wizard" in subtypes:
                return True
        return False
