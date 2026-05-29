"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controller_has_wizard(game: Any, controller: Any) -> bool:
    """Return True if *controller* has a Wizard on the battlefield."""
    if controller is None:
        return False
    bf = game.get_battlefield(controller)
    for card in bf.get_all():
        if "Wizard" in getattr(card, "subtypes", set()):
            return True
    return False


class _OneShotSource:
    """Sentinel object used as the source for a one-shot triggered ability."""


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("keywords", Keyword(0))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack (not a mana ability)."""
        from engine.stack import StackObject

        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    isinstance(obj, StackObject) and not obj.is_mana_ability
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; if controller has Wizard, schedule mana generation."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        stack_obj = chosen[0]

        # Get the source card's CMC before countering
        source_card = stack_obj.source
        cmc = 0
        if source_card is not None:
            mana_cost = getattr(source_card, "mana_cost", None)
            if mana_cost is not None:
                cmc = mana_cost.cmc

        # Counter the spell: remove from stack, put source card in owner's graveyard
        if stack_obj in game.stack.objects():
            game.stack.remove(stack_obj)

        if source_card is not None:
            owner = getattr(source_card, "owner", None)
            if owner is not None:
                graveyard = game.get_graveyard(owner)
                graveyard.add(source_card)

        # Check if controller has a Wizard; if not, no mana generation
        controller = self.controller
        if not _controller_has_wizard(game, controller):
            return

        # Register a one-shot trigger for beginning of next main phase
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        trigger_source = _OneShotSource()
        _cmc = cmc
        _controller = controller

        def _mana_effect(g: "GameState") -> None:
            g.trigger_manager.unregister(trigger_source)
            _controller.mana_pool.add(ManaType.COLORLESS, _cmc)

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=lambda g, e: e.active_player is None or e.active_player is _controller,
            effect=_mana_effect,
            source=trigger_source,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
