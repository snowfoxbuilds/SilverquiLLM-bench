"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    ENGINE LIMITATION: "Add mana at the beginning of your next main phase"
    requires deferred mana-production tracking. This is implemented by
    storing the mana amount on the game state and producing it when the
    controller's next main phase begins. The trigger fires on next
    PRECOMBAT_MAIN BeginningOfUpkeep equivalent — approximated via a
    stored `_pending_mana` dict on the controller.

    SOS collector number 57.
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
        """Target spell on the stack."""
        def _is_spell_on_stack(obj: Any) -> bool:
            # Target is a StackObject; its source should be a card.
            from engine.stack import StackObject
            return isinstance(obj, StackObject)

        return [
            TargetRequirement(
                filter_fn=_is_spell_on_stack,
                description="target spell",
                zone=Zone.STACK,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; optionally add {C} if controller has a Wizard."""
        from engine.stack import StackObject
        from engine.types import ManaType

        controller = self.controller
        targets = getattr(self, "chosen_targets", None) or []
        target_stack_obj = targets[0] if targets else None

        if target_stack_obj is None:
            return

        # Determine CMC of countered spell (used if Wizard bonus applies).
        target_card = getattr(target_stack_obj, "source", None)
        cmc = 0
        if target_card is not None:
            cost = getattr(target_card, "mana_cost", None)
            if cost is not None:
                cmc = cost.cmc

        # Counter the spell: remove from stack, move card to graveyard.
        try:
            game.stack._items.remove(target_stack_obj)
        except ValueError:
            pass  # Already resolved or not on stack

        if target_card is not None:
            target_owner = getattr(target_card, "owner", None) or controller
            # Move from wherever it currently is to graveyard.
            from engine.zones import move_to_zone
            for player in game.players:
                for zone_type in Zone:
                    if player.zones[zone_type].contains(target_card):
                        move_to_zone(game, target_card, zone_type, Zone.GRAVEYARD)
                        break

        # If controller controls a Wizard, schedule deferred {C} production.
        if controller is not None and cmc > 0:
            if self._controller_has_wizard(game, controller):
                # Store pending mana for next main phase.
                if not hasattr(controller, "_pending_mana_next_main"):
                    controller._pending_mana_next_main = 0  # type: ignore[attr-defined]
                controller._pending_mana_next_main += cmc  # type: ignore[attr-defined]

    @staticmethod
    def _controller_has_wizard(game: "GameState", controller: Any) -> bool:
        """Return True if controller controls a permanent with Wizard subtype."""
        bf = game.get_battlefield(controller)
        for permanent in bf.get_all():
            if "Wizard" in getattr(permanent, "subtypes", set()):
                return True
        return False

