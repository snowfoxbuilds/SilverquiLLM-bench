"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class DelayedManaTrigger:
    """A delayed trigger that adds colorless mana at the next main phase.

    Attributes:
        controller: The player who will receive the mana.
        mana_amount: The amount of colorless mana to add.
        amount: Alias for mana_amount (for test compatibility).
    """

    controller: Any
    mana_amount: int

    @property
    def amount(self) -> int:
        return self.mana_amount


def _counter_spell(game: "GameState", target_card: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
    # Find the StackObject whose source is the target card
    stack_items = game.stack._items
    for i, item in enumerate(stack_items):
        if item.source is target_card:
            stack_items.pop(i)
            break

    # Move card to owner's graveyard
    owner = getattr(target_card, "owner", None)
    if owner is not None:
        graveyard = game.get_graveyard(owner)
        graveyard.add(target_card)


def _has_wizard(game: "GameState", player: Any) -> bool:
    """Check if player controls a Wizard creature."""
    bf = game.get_battlefield(player)
    for obj in bf.get_all():
        subtypes = getattr(obj, "subtypes", set())
        if "Wizard" in subtypes:
            return True
    return False


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
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell "
            "at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Require one target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell. If controller has a Wizard, set up delayed trigger."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_card = chosen[0]
        controller = getattr(self, "controller", getattr(self, "owner", None))

        # Counter the spell
        _counter_spell(game, target_card)

        # Check for Wizard bonus
        if controller is not None and _has_wizard(game, controller):
            # Calculate mana value of the countered spell
            target_cost = getattr(target_card, "mana_cost", None)
            if target_cost is not None:
                mana_amount = target_cost.cmc
            else:
                mana_amount = 0

            if mana_amount > 0:
                # Register a delayed trigger
                trigger = DelayedManaTrigger(
                    controller=controller,
                    mana_amount=mana_amount,
                )

                # Ensure game has delayed_triggers list
                if not hasattr(game, "delayed_triggers"):
                    game.delayed_triggers = []
                game.delayed_triggers.append(trigger)
