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
from engine.stack import StackObject

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
        controller: The player who controls the source.
        cost: A callable ``(game, source) -> bool`` that checks and pays
            the cost. Returns ``True`` if the cost was successfully paid,
            ``False`` otherwise.
        effect: A callable ``(game) -> None`` that applies the ability's
            effect when it resolves.
        is_mana_ability: Whether this is a mana ability (resolves
            immediately without using the stack).
        description: Human-readable description of the ability.
    """

    source: Any
    controller: Any  # Player
    cost: Callable[..., bool]
    effect: Callable[..., None]
    is_mana_ability: bool = False
    description: str = ""


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
    # Optional activation targets.  When provided, the engine exposes them
    # to the effect via ``source.chosen_targets`` at resolution time (the
    # same contract spell resolution uses).
    targets: list[Any] | None = None


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

def _activate_regular_ability(
    game: GameState,
    player: Any,
    ability: ActivatedAbilityInstance,
) -> None:
    """Activate a regular (non-loyalty) activated ability."""
    # 1. Check "can't activate" restriction (e.g. Arrest).
    if getattr(ability.source, "_cant_activate", False):
        raise AbilityError(
            "Cannot activate ability — source's activated abilities are suppressed"
        )

    # 2. Pay costs
    cost_paid = ability.cost(game, ability.source)
    if not cost_paid:
        raise AbilityError("Cannot activate ability — cost could not be paid")

    # 3. Resolve or push
    if ability.is_mana_ability:
        # Mana abilities resolve immediately without using the stack.
        ability.effect(game)
    else:
        # Push to stack for resolution.
        stack_obj = StackObject(
            source=ability.source,
            controller=player,
            on_resolve=ability.effect,
            is_mana_ability=False,
        )
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

    # 5. Push to stack.  If the activation carries targets, set them on the
    #    source at resolution time (mirrors how spell resolution exposes
    #    StackObject.targets via card.chosen_targets).
    targets = list(ability.targets) if ability.targets is not None else []
    effect = ability.effect

    def _resolve(g: GameState) -> None:
        if ability.targets is not None:
            source.chosen_targets = targets
        elif hasattr(source, "chosen_targets"):
            # Clear stale targets (e.g. left over from casting the
            # planeswalker) so the effect sees this activation's state.
            del source.chosen_targets
        effect(g)

    stack_obj = StackObject(
        source=source,
        controller=player,
        targets=targets,
        on_resolve=_resolve,
        is_mana_ability=False,
    )
    game.stack.push(stack_obj)


# ---------------------------------------------------------------------------
# Printed-ability activation helper
# ---------------------------------------------------------------------------

def activate_loyalty_ability_by_index(
    game: GameState,
    player: Any,
    source: Any,
    index: int,
    targets: list[Any] | None = None,
) -> None:
    """Activate the *index*-th printed loyalty ability of *source*.

    Bridges the printed :class:`engine.card.LoyaltyAbility` dataclasses
    (returned by ``get_loyalty_abilities``) to the runtime
    :class:`LoyaltyAbilityInstance` consumed by :func:`activate_ability`.
    Abilities are addressed by printed index.

    Raises:
        AbilityError: If *source* has no printed loyalty ability at *index*
            or the activation is illegal (timing, loyalty, once-per-turn).
    """
    printed = getattr(source, "get_loyalty_abilities", lambda: [])()
    if index < 0 or index >= len(printed):
        raise AbilityError(
            f"{getattr(source, 'name', source)!r} has no loyalty ability "
            f"at index {index}"
        )
    ability = printed[index]
    instance = LoyaltyAbilityInstance(
        source=source,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
        targets=targets,
    )
    activate_ability(game, player, instance)
