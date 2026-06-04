"""Card implementation for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _stack_source(obj: Any) -> Any:
    """Return the underlying card for a StackObject, or *obj* itself."""
    return getattr(obj, "source", obj)


def _is_spell(obj: Any) -> bool:
    """Return ``True`` if *obj* (a StackObject) represents a cast *spell*.

    "Counter target spell" may only target spells — not activated or
    triggered abilities. In this engine an ability's :class:`StackObject`
    reuses its source permanent's ``card_types`` (e.g. ``{CREATURE}`` for an
    ability whose source is a creature), so a ``card_types`` test cannot
    distinguish a spell from an ability. The casting pipeline marks genuine
    spell StackObjects with ``is_spell=True`` (defaulting ``False`` for
    abilities), so we key off that additive flag.

    A countered spell must still actually be a spell (not a bare land), so we
    additionally require the source to carry at least one non-land card type.
    """
    if getattr(obj, "is_spell", False) is not True:
        return False
    source = _stack_source(obj)
    card_types = getattr(source, "card_types", set())
    return bool(card_types - {CardType.LAND})


def _get_chosen_target(card: Any) -> Any:
    """Retrieve the first chosen target for this spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove its StackObject and route the card to its
    owner's graveyard. The spell never resolves."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return ``True`` if *player* controls a creature with the Wizard subtype."""
    if player is None:
        return False
    battlefield = player.zones[Zone.BATTLEFIELD]
    for obj in battlefield.get_all():
        card_types = getattr(obj, "card_types", set())
        if CardType.CREATURE not in card_types:
            continue
        subtypes = getattr(obj, "subtypes", set()) or set()
        if "Wizard" in subtypes:
            return True
    return False


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
        self.colors = ["U"]
        # Amount of {C} this spell scheduled to be reimbursed at its
        # controller's next main phase (read back by tests; defaults to 0).
        self.pending_colorless: int = 0

    # ------------------------------------------------------------------
    # Targeting — "Counter target spell"
    # ------------------------------------------------------------------

    def can_cast(self, game: "GameState") -> bool:
        """Castable only when there is a legal spell to counter on the stack."""
        for stack_obj in game.stack.objects():
            if _stack_source(stack_obj) is self:
                continue
            if _is_spell(stack_obj):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target any spell on the stack (creature or noncreature)."""

        def _filter(obj: Any) -> bool:
            if obj is self or _stack_source(obj) is self:
                return False
            return _is_spell(obj)

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell; if controlling a Wizard, schedule the
        deferred {C} reimbursement for the controller's next main phase."""
        target = _get_chosen_target(self)
        if target is None:
            return

        # Capture the amount of mana spent on the countered spell BEFORE it
        # leaves the stack (the engine records this as card.mana_spent during
        # payment).
        countered_card = _stack_source(target)
        mana_spent = int(getattr(countered_card, "mana_spent", 0) or 0)

        # Always counter the target spell — unconditional.
        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        # Wizard gate — only schedule the deferred {C} if the controller
        # controls a Wizard at resolution.
        if not _controls_wizard(game, controller):
            self.pending_colorless = 0
            return

        self.pending_colorless = mana_spent
        if mana_spent <= 0:
            return

        def _reimburse(g: "GameState", amount: int = mana_spent, who: Any = controller) -> None:
            who.mana_pool.add(ManaType.COLORLESS, amount)

        # Deferred — not added immediately. Delivered when the controller's
        # next BeginningOfMainPhaseTriggeredEvent (precombat) fires.
        game.schedule_main_phase_deferred_effect(
            controller, _reimburse, precombat=True
        )
