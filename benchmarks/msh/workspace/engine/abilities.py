"""Activated abilities system — tap-for-mana, loyalty abilities, and general
activated abilities that go on the stack (or resolve immediately for mana
abilities).

Provides:

- :func:`activate_ability` — verify timing → pay costs → resolve immediately
  (mana abilities) or push to the stack (non-mana abilities).
- :func:`tap_cost` — generic tap-cost helper: checks ``not source.is_tapped``
  and taps the source.
- :class:`ActivatedAbilityInstance` — a runtime representation of an activated
  ability with source, controller, cost/effect callables, and metadata.
- :class:`LoyaltyAbilityInstance` — activated ability variant for planeswalker
  loyalty abilities with per-turn restriction and loyalty-counter cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from engine.casting import is_sorcery_speed
from engine.stack import ActivationContext, StackObject
from engine.types import Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class AbilityError(Exception):
    """Raised when an ability activation is illegal."""


# ---------------------------------------------------------------------------
# Runtime ability representations
# ---------------------------------------------------------------------------

@dataclass
class ActivatedAbilityInstance:
    """Runtime representation of an activated ability.

    This captures everything needed to activate and resolve an ability:
    the source permanent, the controlling player, cost/effect callables,
    and whether the ability is a mana ability.

    Attributes:
        source: The permanent that has this ability.
        controller: The player activating the ability — its authoritative
            controller (rule 602.2). :func:`activate_ability` must be called
            with this same player; a mismatch is rejected before any query,
            payment, or stack mutation. This controller (never the source's
            possibly-different current controller) is threaded into the
            ``targeting``/``can_activate`` hooks, the cost, the captured
            :class:`~engine.stack.ActivationContext`, and the resulting
            :class:`~engine.stack.StackObject`.
        cost: A callable ``(game, source) -> bool`` that checks and pays
            the cost. Returns ``True`` if the cost was successfully paid,
            ``False`` otherwise.
        effect: A callable that applies the ability's effect when it resolves.
            Invoked ``effect(game)`` for an untargeted ability, or
            ``effect(game, targets, context)`` when ``targeting`` is set — the
            targets are the ones chosen at activation and stored on the stack
            object, and *context* is the :class:`~engine.stack.ActivationContext`
            captured at activation.
        is_mana_ability: Whether this is a mana ability (resolves
            immediately without using the stack).
        description: Human-readable description of the ability.
        targeting: Optional callable ``(game, source, controller) -> list | None``
            run **at activation, before costs are paid**. Returns the chosen
            targets, or ``None`` to signal no legal target (the ability then
            cannot be activated and no cost is spent). The result is stored on
            the :class:`~engine.stack.StackObject` and passed to ``effect`` at
            resolution — the target is never re-selected there. When set, the
            effect is invoked ``effect(game, targets, context)`` where *context*
            is the :class:`~engine.stack.ActivationContext` captured at activation.
        can_activate: Optional callable ``(game, source, controller) -> bool``
            checked **before** any target query is raised or any cost is paid
            (rule 602.2a). Verifies source-zone and timing restrictions with no
            side effects, so an illegal-timing activation raises no query and
            spends no resources. ``None`` means no extra restriction beyond the
            source's ``_cant_activate`` suppression.
    """

    source: Any
    controller: Any  # Player
    cost: Callable[..., bool]
    effect: Callable[..., None]
    is_mana_ability: bool = False
    description: str = ""
    targeting: Callable[..., Any] | None = None
    can_activate: Callable[..., bool] | None = None


@dataclass
class LoyaltyAbilityInstance:
    """Runtime representation of a planeswalker loyalty ability.

    Loyalty abilities are activated abilities with special restrictions:
    they may only be activated at sorcery speed, and only once per turn
    per source (tracked via ``_activated_this_turn``).

    The cost adjusts the loyalty counters on the source planeswalker.

    Attributes:
        source: The planeswalker permanent.
        controller: The player who controls the planeswalker.
        loyalty_cost: The loyalty adjustment (positive for ``+N``,
            negative for ``−N``, zero for ``0``).
        effect: A callable ``(game) -> None`` for the ability's effect.
        description: Human-readable description.
    """

    source: Any
    controller: Any  # Player
    loyalty_cost: int = 0
    effect: Callable[..., None] = field(default=lambda _game: None)
    description: str = ""


# ---------------------------------------------------------------------------
# Per-turn loyalty tracking
# ---------------------------------------------------------------------------

# Set of (object_id, turn_number) pairs that have already activated a
# loyalty ability this turn.  Callers should call
# ``clear_loyalty_tracking()`` at the start of each turn or manage the
# set externally.
_loyalty_activated_this_turn: set[tuple[int, int]] = set()


def clear_loyalty_tracking() -> None:
    """Clear the loyalty-activated-this-turn tracker.

    Should be called at the start of each turn so that planeswalkers may
    activate loyalty abilities again.
    """
    _loyalty_activated_this_turn.clear()


def _has_activated_loyalty_this_turn(source: Any, turn_number: int) -> bool:
    """Return ``True`` if *source* already used a loyalty ability this turn."""
    obj_id = getattr(source, "object_id", id(source))
    return (obj_id, turn_number) in _loyalty_activated_this_turn


def _mark_loyalty_activated(source: Any, turn_number: int) -> None:
    """Record that *source* used a loyalty ability this turn."""
    obj_id = getattr(source, "object_id", id(source))
    _loyalty_activated_this_turn.add((obj_id, turn_number))


# ---------------------------------------------------------------------------
# Tap cost helper
# ---------------------------------------------------------------------------

def tap_cost(game: GameState, source: Any) -> bool:
    """Generic tap-cost function.

    Checks that the source is not already tapped.  If untapped, taps it
    (sets ``source.is_tapped = True``) and returns ``True``.  If already
    tapped, returns ``False`` (cost cannot be paid).

    Parameters:
        game: The current game state (unused here but kept for a
            consistent ``(game, source) -> bool`` cost signature).
        source: The permanent to tap.

    Returns:
        ``True`` if the cost was successfully paid (source was untapped
        and is now tapped), ``False`` otherwise.
    """
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


# ---------------------------------------------------------------------------
# Activate ability — main entry point
# ---------------------------------------------------------------------------

def activate_ability(
    game: GameState,
    player: Any,  # Player
    ability: ActivatedAbilityInstance | LoyaltyAbilityInstance,
) -> None:
    """Activate an ability.

    Pipeline
    --------
    1. **Timing check** — mana abilities bypass timing entirely and
       resolve immediately.  Regular (non-mana) activated abilities
       can be activated whenever a player has priority (instant speed);
       priority enforcement is handled externally by
       ``priority_loop``, not here.  **Only loyalty abilities** carry
       a sorcery-speed restriction.
    2. **Pay costs** — invoke the ability's cost callable.  For loyalty
       abilities, adjust loyalty counters and enforce once-per-turn.
    3. **Resolve or push to stack** — mana abilities resolve
       immediately; all other abilities are pushed onto the game stack
       as :class:`StackObject` instances.

    Parameters:
        game: The current game state.
        player: The player activating the ability.
        ability: The ability to activate (an
            :class:`ActivatedAbilityInstance` or
            :class:`LoyaltyAbilityInstance`).

    Raises:
        AbilityError: If the activation is illegal (timing, cost, or
            once-per-turn restriction).
    """
    if isinstance(ability, LoyaltyAbilityInstance):
        _activate_loyalty_ability(game, player, ability)
    elif isinstance(ability, ActivatedAbilityInstance):
        _activate_regular_ability(game, player, ability)
    else:
        raise AbilityError(f"Unknown ability type: {type(ability)}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _battlefield_instance_id(game: GameState, obj: Any) -> int | None:
    """Return *obj*'s current battlefield stint id, or ``None`` if it is not on
    any player's battlefield.

    A zone change mints a fresh stint id (see ``GameRefsRegistry.instance_id``),
    so a snapshot taken here at activation lets a resolving effect tell whether
    the same Python object is still the *same* battlefield permanent it was when
    the ability was activated — a leave-and-return yields a different id.
    """
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return game.refs.instance_id(obj, Zone.BATTLEFIELD.value)
    return None


def _capture_activation_context(
    game: GameState,
    source: Any,
    controller: Any,
    targets: list[Any],
) -> ActivationContext:
    """Snapshot the activation-time controller and source/target stints (rule
    602.2). Stored on the :class:`StackObject`, never on the mutable source."""
    return ActivationContext(
        controller=controller,
        source_instance_id=_battlefield_instance_id(game, source),
        target_instance_ids=tuple(
            _battlefield_instance_id(game, t) for t in targets
        ),
    )


def _activate_regular_ability(
    game: GameState,
    player: Any,
    ability: ActivatedAbilityInstance,
) -> None:
    """Activate a regular (non-loyalty) activated ability.

    Sequence (rule 602.2): authorization → legality → target selection → cost
    payment → push. Authorization and legality are verified *before* any target
    query is raised or any cost is paid, so an illegal or unauthorized
    activation (wrong player, wrong timing, source off the battlefield) consumes
    no target intent and spends no resources.
    """
    source = ability.source

    # 1. Authorization (rule 602.2): the player activating the ability *is* its
    #    controller, and that must be the ability's declared controller. We do
    #    not silently substitute the source's current controller here — a
    #    permanent's controller is not automatically entitled to activate an
    #    instance another player set up, and authorization must never rewrite
    #    who the activating player is. Whether that controller may *legally*
    #    activate this ability (e.g. does it actually control the source?) is a
    #    ``can_activate`` concern, checked below. The authorized controller is
    #    the one threaded into targeting, the cost, the activation context, and
    #    the stack object.
    controller = ability.controller if ability.controller is not None else player
    if player is not controller:
        raise AbilityError(
            "Cannot activate ability — the activating player is not the "
            "ability's controller"
        )

    # 2. Check "can't activate" restriction (e.g. Arrest).
    if getattr(source, "_cant_activate", False):
        raise AbilityError(
            "Cannot activate ability — source's activated abilities are suppressed"
        )

    # 3. Activation legality — source-zone and timing restrictions (rule
    #    602.2a), checked BEFORE raising any target query or paying any cost.
    if ability.can_activate is not None and not ability.can_activate(
        game, source, controller
    ):
        raise AbilityError(
            "Cannot activate ability — activation is illegal (timing or zone)"
        )

    # 4. Choose targets (rule 602.2b/2c) — BEFORE paying costs, so an ability
    #    with no legal target cannot be activated and spends no mana. The chosen
    #    targets are stored on the stack object and are not re-selected at
    #    resolution (see KEY_DECISIONS: activation-time ability targeting).
    chosen_targets: list[Any] = []
    context: ActivationContext | None = None
    if ability.targeting is not None:
        # Mana abilities cannot target (rule 605.1a); reject the combination
        # explicitly rather than calling the wrong effect signature.
        if ability.is_mana_ability:
            raise AbilityError("A mana ability cannot target")
        chosen = ability.targeting(game, source, controller)
        if chosen is None:
            raise AbilityError("Cannot activate ability — no legal target")
        chosen_targets = list(chosen)
        # 5. Capture the immutable activation context (authorized controller +
        #    source/target stints) now, while the source and targets are in
        #    their activation zones, and before the cost mutates anything.
        context = _capture_activation_context(game, source, controller, chosen_targets)

    # 6. Pay costs
    cost_paid = ability.cost(game, source)
    if not cost_paid:
        raise AbilityError("Cannot activate ability — cost could not be paid")

    # 7. Resolve or push
    if ability.is_mana_ability:
        # Mana abilities resolve immediately without using the stack.
        ability.effect(game)
    else:
        # Push to stack for resolution. A targeted ability's effect reads the
        # activation-time targets and context off the stack object; an untargeted
        # effect keeps the historical ``effect(game)`` signature.
        stack_obj = StackObject(
            source=source,
            controller=controller,
            targets=chosen_targets,
            is_mana_ability=False,
            activation_context=context,
        )
        if ability.targeting is not None:
            effect = ability.effect
            stack_obj.on_resolve = (
                lambda g, _obj=stack_obj, _effect=effect: _effect(
                    g, _obj.targets, _obj.activation_context
                )
            )
        else:
            stack_obj.on_resolve = ability.effect
        game.stack.push(stack_obj)


def _activate_loyalty_ability(
    game: GameState,
    player: Any,
    ability: LoyaltyAbilityInstance,
) -> None:
    """Activate a planeswalker loyalty ability."""
    source = ability.source

    # 1. Timing — loyalty abilities are sorcery speed only.
    if not is_sorcery_speed(game, player):
        raise AbilityError(
            "Cannot activate loyalty ability — sorcery-speed timing not met"
        )

    # 2. Once-per-turn restriction.
    turn_number = getattr(game, "turn_number", 0)
    if _has_activated_loyalty_this_turn(source, turn_number):
        raise AbilityError(
            "Cannot activate loyalty ability — already activated this turn"
        )

    # 3. Pay loyalty cost.
    current_loyalty = getattr(source, "loyalty", 0)
    new_loyalty = current_loyalty + ability.loyalty_cost
    if new_loyalty < 0:
        raise AbilityError(
            f"Cannot activate loyalty ability — insufficient loyalty "
            f"(have {current_loyalty}, need {-ability.loyalty_cost})"
        )
    source.loyalty = new_loyalty

    # 4. Mark as activated this turn.
    _mark_loyalty_activated(source, turn_number)

    # 5. Push to stack.
    stack_obj = StackObject(
        source=source,
        controller=player,
        on_resolve=ability.effect,
        is_mana_ability=False,
    )
    game.stack.push(stack_obj)
