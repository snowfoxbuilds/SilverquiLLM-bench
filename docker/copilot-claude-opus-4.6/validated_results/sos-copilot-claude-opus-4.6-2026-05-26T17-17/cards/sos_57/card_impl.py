"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _DelayedManaTriger:
    """A delayed trigger that produces colorless mana."""

    def __init__(self, mana_amount: int) -> None:
        self.mana_amount = mana_amount


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add colorless mana
    equal to mana spent to cast that spell at your next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; conditionally schedule mana refund."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        target_spell = chosen[0]
        mana_spent = getattr(target_spell, "mana_spent", 0)

        # Counter the spell (move to graveyard)
        target_spell.zone = Zone.GRAVEYARD
        owner = getattr(target_spell, "owner", None)
        if owner is not None:
            game.get_graveyard(owner).add(target_spell)

        # Check if controller controls a Wizard
        controller = self.controller
        if controller is None:
            return

        bf = game.get_battlefield(controller)
        has_wizard = False
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                if "Wizard" in getattr(obj, "subtypes", set()):
                    has_wizard = True
                    break

        if has_wizard and mana_spent > 0:
            trigger = _DelayedManaTriger(mana_amount=mana_spent)
            game.add_delayed_trigger(controller, trigger)
