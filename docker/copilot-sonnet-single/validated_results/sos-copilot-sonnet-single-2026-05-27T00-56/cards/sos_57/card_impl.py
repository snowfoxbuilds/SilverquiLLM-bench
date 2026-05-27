"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            (
                "Counter target spell. If you control a Wizard, add an amount of {C} "
                "equal to the amount of mana spent to cast that spell at the beginning "
                "of your next main phase."
            ),
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return a single target requirement: a spell on the stack."""
        from engine.stack import StackObject

        req = TargetRequirement(
            filter_fn=lambda obj: isinstance(obj, StackObject),
            description="target spell",
            zone=Zone.STACK,
        )
        return [req]

    def _controls_wizard(self, game: "GameState", player: Any) -> bool:
        """Return True if *player* controls a Wizard on the battlefield."""
        bf = game.get_battlefield(player)
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                if "Wizard" in getattr(obj, "subtypes", set()):
                    return True
        return False

    def on_resolve(self, game: "GameState") -> None:
        """Counter the targeted spell; if controller has a Wizard, register
        a delayed trigger to add colorless mana at the next main phase."""
        from engine.zones import move_to_zone

        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return

        target_stack_obj = targets[0]
        target_card = target_stack_obj.source

        # Remove the targeted spell from the game stack (counter it).
        try:
            game.stack.remove(target_stack_obj)
        except ValueError:
            pass  # Already removed or not on stack

        # Move the countered spell's card to its owner's graveyard.
        owner = getattr(target_card, "owner", None)
        if owner is not None and owner.zones[Zone.STACK].contains(target_card):
            move_to_zone(game, target_card, Zone.STACK, Zone.GRAVEYARD)

        # Check Wizard condition.
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        if not self._controls_wizard(game, controller):
            return

        # Register a delayed trigger: at the beginning of the controller's
        # next main phase, add colorless mana equal to the CMC of the countered spell.
        cmc = target_card.mana_cost.cmc
        spell_source = self
        ctrl_ref = controller

        def _mana_effect(game: "GameState") -> None:
            ctrl_ref.mana_pool.add(ManaType.COLORLESS, cmc)
            # One-shot: unregister after firing so it doesn't repeat.
            game.trigger_manager.unregister(spell_source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=lambda game, event: game.active_player is ctrl_ref,
                effect=_mana_effect,
                source=spell_source,
                controller=ctrl_ref,
            )
        )
