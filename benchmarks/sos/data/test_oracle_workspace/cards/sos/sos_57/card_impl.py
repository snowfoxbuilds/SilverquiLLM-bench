"""Card implementation for Mana Sculpt.

Mana Sculpt — {1}{U}{U} — Instant (Rare)
Counter target spell. If you control a Wizard, add an amount of {C}
equal to the amount of mana spent to cast that spell at the beginning
of your next main phase.

Xmage analog: Mana Drain (counter + delayed-trigger refund) + Arcane
Epiphany (Wizard-conditional).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("mana_cost", ManaCost(generic=1, pips={ManaType.BLUE: 2}))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return spells on the stack as legal targets (not abilities)."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            # Only target spells (cards being cast), not activated/triggered abilities.
            # Spells have a source card with card_types defined.
            source = getattr(stack_obj, "source", None)
            if source is not None and hasattr(source, "card_types"):
                targets.append(stack_obj)
        return targets

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell. Wizard-conditional mana refund."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_stack_obj = chosen[0]

        # Fizzle check: if the target is no longer on the stack, do nothing.
        stack_items = game.stack._items
        if target_stack_obj not in stack_items:
            return

        # Remove target from the stack (counter it)
        stack_items.remove(target_stack_obj)

        # Move the spell card to owner's graveyard (countering)
        source_card = getattr(target_stack_obj, "source", None)
        if source_card is not None:
            owner = getattr(source_card, "owner", None)
            controller = getattr(source_card, "controller", owner)
            # Remove from stack zone if present
            if owner is not None and hasattr(owner, "zones"):
                stack_zone = owner.zones[Zone.STACK]
                if stack_zone.contains(source_card):
                    stack_zone.remove(source_card)
            elif controller is not None and hasattr(controller, "zones"):
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(source_card):
                    stack_zone.remove(source_card)
            # Move to owner's graveyard
            if owner is not None and hasattr(owner, "zones"):
                gy = owner.zones[Zone.GRAVEYARD]
                gy.add(source_card)

        # Wizard-conditional mana refund: if controller controls a Wizard,
        # add colorless mana equal to countered spell's CMC.
        my_controller = getattr(self, "controller", None)
        if my_controller is not None and source_card is not None:
            battlefield = my_controller.zones[Zone.BATTLEFIELD]
            if battlefield is not None:
                has_wizard = any(
                    "Wizard" in getattr(perm, "subtypes", set())
                    for perm in battlefield.get_all()
                )
                if has_wizard:
                    cmc = getattr(getattr(source_card, "mana_cost", None), "cmc", 0)
                    if cmc > 0:
                        my_controller.mana_pool.add(ManaType.COLORLESS, cmc)
