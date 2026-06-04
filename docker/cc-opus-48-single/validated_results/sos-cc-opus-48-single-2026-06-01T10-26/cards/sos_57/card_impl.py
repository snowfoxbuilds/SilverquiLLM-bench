"""Card implementation for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# Card types that identify an object on the stack as a "spell".
_SPELL_TYPES = frozenset(
    {
        CardType.INSTANT,
        CardType.SORCERY,
        CardType.CREATURE,
        CardType.ENCHANTMENT,
        CardType.ARTIFACT,
        CardType.PLANESWALKER,
    }
)


def _is_spell(obj: Any) -> bool:
    """Return ``True`` if *obj* is a castable spell (not a player/permanent-only).

    "Target spell" is not "any target": players are illegal, and the object
    must carry spell card types.
    """
    if obj is None:
        return False
    # Players expose ``life`` — reject them ("target spell" excludes players).
    if hasattr(obj, "life"):
        return False
    card_types = getattr(obj, "card_types", None)
    if not card_types:
        return False
    return bool(card_types & _SPELL_TYPES)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return ``True`` if *player* controls a creature with the Wizard subtype."""
    if player is None:
        return False
    battlefield = player.zones[Zone.BATTLEFIELD]
    for obj in battlefield.get_all():
        subtypes = getattr(obj, "subtypes", set()) or set()
        if "Wizard" in subtypes:
            return True
    return False


def _mana_spent_on(spell: Any) -> int:
    """Return the amount of mana spent to cast *spell*.

    Prefers the engine-recorded ``mana_spent`` (the actual total mana paid;
    see :attr:`engine.mana.ManaPool.last_payment_total`). Falls back to the
    printed mana value when the spell was not cast through the normal
    payment pipeline (e.g. placed on the stack directly in tests).
    """
    recorded = getattr(spell, "mana_spent", None)
    if recorded is not None:
        return int(recorded)
    cost = getattr(spell, "mana_cost", None)
    if cost is not None:
        return int(cost.cmc)
    return 0


def _counter_spell(game: "GameState", target_spell: Any) -> None:
    """Counter *target_spell*: remove its StackObject and move it to the
    owner's graveyard. The spell never resolves."""
    stack_items = game.stack._items  # noqa: SLF001
    stack_obj = None
    for item in list(stack_items):
        if getattr(item, "source", None) is target_spell:
            stack_obj = item
            break
    if stack_obj is None:
        return

    stack_items.remove(stack_obj)

    owner = getattr(target_spell, "owner", None) or getattr(stack_obj, "controller", None)
    controller = getattr(stack_obj, "controller", None) or owner

    # Remove the card from whatever STACK zone it lives in.
    if controller is not None and controller.zones[Zone.STACK].contains(target_spell):
        controller.zones[Zone.STACK].remove(target_spell)
    elif owner is not None and owner.zones[Zone.STACK].contains(target_spell):
        owner.zones[Zone.STACK].remove(target_spell)

    # A countered spell is put into its owner's graveyard.
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(target_spell)


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Advertise a single 'target spell' requirement on the stack."""
        return [
            TargetRequirement(
                filter_fn=_is_spell,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the targeted spell, then (if a Wizard is controlled) set up
        the delayed colorless-mana payoff."""
        chosen = getattr(self, "chosen_targets", None) or []
        if not chosen:
            # No legal target chosen — safe no-op.
            return
        target_spell = chosen[0]
        if target_spell is None:
            return

        # Capture the amount of mana spent before the spell leaves the stack.
        mana_spent = _mana_spent_on(target_spell)

        _counter_spell(game, target_spell)

        controller = self.controller
        if controller is None:
            return

        # "If you control a Wizard" — checked at resolution.
        if not _controls_wizard(game, controller):
            return

        self._register_delayed_mana(game, controller, mana_spent)

    def _register_delayed_mana(
        self, game: "GameState", controller: Any, amount: int
    ) -> None:
        """Register a delayed trigger that adds ``amount`` {C} to *controller*'s
        pool at the beginning of their next main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        fired = {"done": False}

        def _condition(g: "GameState", event: Any) -> bool:
            if fired["done"]:
                return False
            return getattr(event, "player", None) is controller

        def _effect(g: "GameState") -> None:
            fired["done"] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            # One-shot: remove this delayed effect once it has fired.
            g.trigger_manager.unregister(self)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
