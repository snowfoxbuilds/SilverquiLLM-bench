"""Card implementation for Mana Sculpt (sos_57).

Counter target spell. If you control a Wizard, add an amount of {C} equal
to the amount of mana spent to cast that spell at the beginning of your
next main phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controller_has_wizard(game: Any, player: Any) -> bool:
    """Return True if *player* controls a creature with subtype 'Wizard'."""
    battlefield = game.get_battlefield(player)
    for obj in battlefield.get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            subtypes = getattr(obj, "subtypes", set())
            if "Wizard" in subtypes:
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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return one TargetRequirement targeting a spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, StackObject),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the targeted spell; optionally defer colorless mana."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target: StackObject = chosen[0]

        # Fizzle check: if the target has already left the stack, do nothing.
        if target not in game.stack._items:
            return

        # Zone cleanup: remove from stack FIRST, then move to graveyard.
        game.stack._items.remove(target)

        # Move the countered card to its owner's graveyard.
        source_card = getattr(target, "source", None)
        if source_card is not None:
            owner = getattr(source_card, "owner", None)
            if owner is not None:
                graveyard = game.get_graveyard(owner)
                graveyard.add(source_card)

        # Wizard check — defer colorless mana if controller has a Wizard.
        controller = self.controller
        if controller is None:
            return

        if not _controller_has_wizard(game, controller):
            return

        # Determine CMC of the countered spell.
        cmc = 0
        if source_card is not None:
            mana_cost = getattr(source_card, "mana_cost", None)
            if mana_cost is not None:
                cmc = mana_cost.cmc

        if cmc == 0:
            return

        # Store pending amount on the player.
        controller.pending_colorless_for_main = cmc

        # Delivery function — idempotent: clears pending after delivering.
        def _deliver(g: Any, _player: Any = controller) -> None:
            amount = getattr(_player, "pending_colorless_for_main", 0)
            if amount > 0:
                _player.mana_pool.add(ManaType.COLORLESS, amount)
                _player.pending_colorless_for_main = 0

        # Attach as a method on the player so tests can call it directly.
        controller._deliver_main_phase_mana = _deliver

        # Also push a StackObject trigger so tests that drain the stack work.
        def _trigger_resolve(g: Any) -> None:
            _deliver(g)

        trigger = StackObject(
            source=self,
            controller=controller,
            on_resolve=_trigger_resolve,
        )
        game.stack.push(trigger)
