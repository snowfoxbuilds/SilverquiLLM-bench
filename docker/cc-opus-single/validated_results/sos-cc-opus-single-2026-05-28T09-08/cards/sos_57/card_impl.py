"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.triggers import TriggerRegistration
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt -- {1}{U}{U} -- Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell "
            "at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Targeting -- target spell on the stack
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell (any object on the stack)."""
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
        """Counter the target spell; if we control a Wizard, set up a
        delayed trigger for a mana rebate of {C} equal to the countered
        spell's CMC."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_spell = chosen[0]
        if target_spell is None:
            return

        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        # Capture mana spent (CMC of the countered spell) before moving it
        mana_spent = getattr(target_spell, "mana_cost", None)
        rebate_amount = mana_spent.cmc if mana_spent is not None else 0

        # Counter the spell: move it from the stack zone to its owner's graveyard
        spell_owner = getattr(target_spell, "owner", None)
        if spell_owner is not None:
            # Remove from the stack zone
            if spell_owner.zones[Zone.STACK].contains(target_spell):
                spell_owner.zones[Zone.STACK].remove(target_spell)
            # Put into the owner's graveyard
            spell_owner.zones[Zone.GRAVEYARD].add(target_spell)

        # Check if the controller controls a Wizard
        if not self._controls_wizard(game, controller):
            return

        # Register a one-shot delayed trigger for the mana rebate
        # at the beginning of controller's next main phase.
        source = self
        amount = rebate_amount

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            """Only fire when it is the controller's main phase."""
            return getattr(event, "player", None) is controller

        def _effect(game: "GameState") -> None:
            """Add {C} equal to the countered spell's CMC to the controller's pool,
            then unregister so this one-shot trigger does not fire again."""
            if amount > 0:
                controller.mana_pool.add(ManaType.COLORLESS, amount)
            # One-shot: remove this delayed trigger after firing
            game.trigger_manager.unregister(source)

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=controller,
        )
        game.trigger_manager.register(trigger)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _controls_wizard(game: "GameState", player: Any) -> bool:
        """Return True if *player* controls a permanent with the Wizard subtype."""
        battlefield = game.get_battlefield(player)
        for obj in battlefield.get_all():
            subtypes = getattr(obj, "subtypes", set())
            if "Wizard" in subtypes:
                return True
        return False
