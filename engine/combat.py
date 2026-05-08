"""Combat system: declare attackers → declare blockers → damage → end combat.

Implements the four substeps of the MTG combat phase:

1. **Declare Attackers** — Active player chooses creatures to attack with.
   Attackers are tapped (unless they have vigilance).  Creatures with
   summoning sickness (without haste) or the defender keyword cannot attack.

2. **Declare Blockers** — Defending player assigns blockers.  Creatures
   with flying can only be blocked by creatures with flying or reach.
   Creatures with menace require 2+ blockers.  The attacker's controller
   orders the blockers for damage assignment.

3. **Combat Damage** — First strike / double strike creatures deal damage
   first, then state-based actions are checked, then normal damage.
   Trample excess goes to the defending player.  Lifelink heals the
   controller.  Deathtouch makes any nonzero damage lethal.  Unblocked
   attackers deal damage to the defending player.

4. **End Combat** — Clear all combat state.

References: MTG Comprehensive Rules §506–§511.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine.types import Keyword

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# ---------------------------------------------------------------------------
# CombatState — tracks all per-combat information
# ---------------------------------------------------------------------------

@dataclass
class CombatState:
    """Tracks attackers, blockers, damage assignments, and block ordering.

    Attributes:
        attackers: Mapping of attacking creature → defending player.
        blockers: Mapping of blocking creature → list of attackers it blocks.
        attacker_blockers: Mapping of attacking creature → ordered list of
            blockers assigned to it (order used for damage assignment).
        damage_assignments: Mapping of creature → list of
            ``(target, amount)`` tuples describing how damage is assigned.
        was_blocked: Set of attackers that were declared as blocked.  Per
            MTG rule 509.1h, once a creature is blocked it stays blocked
            even if all its blockers are removed before damage.
        in_combat: Whether the combat phase is currently active.
    """

    attackers: dict[Any, Player] = field(default_factory=dict)
    blockers: dict[Any, list[Any]] = field(default_factory=dict)
    attacker_blockers: dict[Any, list[Any]] = field(default_factory=dict)
    damage_assignments: dict[Any, list[tuple[Any, int]]] = field(default_factory=dict)
    was_blocked: set[Any] = field(default_factory=set)
    in_combat: bool = False

    def clear(self) -> None:
        """Reset all combat state."""
        self.attackers.clear()
        self.blockers.clear()
        self.attacker_blockers.clear()
        self.damage_assignments.clear()
        self.was_blocked.clear()
        self.in_combat = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _can_attack(creature: Any) -> bool:
    """Return ``True`` if *creature* is eligible to be declared as an attacker.

    A creature cannot attack if:
    - It is already tapped.
    - It has the ``DEFENDER`` keyword.
    - It has summoning sickness (``summoning_sick``) and does not have ``HASTE``.
    - A continuous effect has set ``_cant_attack`` (e.g. Pacifism).
    """
    if getattr(creature, "is_tapped", False):
        return False

    # Check for "can't attack" restriction (set by continuous effects like Pacifism)
    if getattr(creature, "_cant_attack", False):
        return False

    keywords = getattr(creature, "keywords", Keyword(0))

    if Keyword.DEFENDER in keywords:
        return False

    if getattr(creature, "summoning_sick", False) and Keyword.HASTE not in keywords:
        return False

    return True


def _can_block(blocker: Any, attacker: Any) -> bool:
    """Return ``True`` if *blocker* can legally block *attacker*.

    Checks:
    - If the blocker is tapped it cannot block.
    - A continuous effect has set ``_cant_block`` (e.g. Pacifism).
    - If the attacker has flying, the blocker must have flying or reach.
    """
    if getattr(blocker, "is_tapped", False):
        return False

    # Check for "can't block" restriction (set by continuous effects like Pacifism)
    if getattr(blocker, "_cant_block", False):
        return False

    attacker_kw = getattr(attacker, "keywords", Keyword(0))
    blocker_kw = getattr(blocker, "keywords", Keyword(0))

    # Flying check
    if Keyword.FLYING in attacker_kw:
        if Keyword.FLYING not in blocker_kw and Keyword.REACH not in blocker_kw:
            return False

    return True


def _get_lethal_damage(creature: Any, attacker: Any | None = None) -> int:
    """Return the amount of damage needed to lethally assign to *creature*.

    If *attacker* has deathtouch, 1 damage is lethal.
    Otherwise it's ``toughness - damage_marked`` (at least 1).
    """
    if attacker is not None:
        attacker_kw = getattr(attacker, "keywords", Keyword(0))
        if Keyword.DEATHTOUCH in attacker_kw:
            return 1

    toughness = getattr(creature, "toughness", 0)
    damage_marked = getattr(creature, "damage_marked", 0)
    return max(1, toughness - damage_marked)


def _deal_damage(
    source: Any,
    target: Any,
    amount: int,
    game: GameState,
    combat_state: CombatState,
) -> None:
    """Apply *amount* damage from *source* to *target*.

    If *target* is a player, reduces life.
    If *target* is a creature, marks damage on it.
    If *source* has lifelink, the controller gains that much life.
    """
    if amount <= 0:
        return

    # Record damage assignment
    if source not in combat_state.damage_assignments:
        combat_state.damage_assignments[source] = []
    combat_state.damage_assignments[source].append((target, amount))

    # Apply damage
    if hasattr(target, "life"):
        # Target is a player
        target.life -= amount
    elif hasattr(target, "damage_marked"):
        # Target is a creature
        target.damage_marked += amount

        # Track deathtouch damage for SBA rule 704.5h
        source_kw_dt = getattr(source, "keywords", Keyword(0))
        if Keyword.DEATHTOUCH in source_kw_dt:
            target.dealt_deathtouch_damage = True

    # Lifelink: controller gains life equal to damage dealt
    source_kw = getattr(source, "keywords", Keyword(0))
    if Keyword.LIFELINK in source_kw:
        controller = getattr(source, "controller", None)
        if controller is not None and hasattr(controller, "life"):
            controller.life += amount


# ---------------------------------------------------------------------------
# Combat steps
# ---------------------------------------------------------------------------

def declare_attackers_step(game: GameState) -> None:
    """Declare attackers step: active player chooses creatures to attack with.

    The active player is asked (via :meth:`Player.choose`) to select a set
    of creatures to attack with.  Each chosen attacker is tapped (unless it
    has vigilance) and its ``is_attacking`` flag is set.

    Parameters:
        game: The current game state.  ``game.combat_state`` must exist.
    """
    combat = game.combat_state
    combat.in_combat = True
    active = game.active_player
    defending = game.non_active_player

    # Gather legal attackers from the active player's battlefield
    from engine.types import Zone
    bf = active.zones[Zone.BATTLEFIELD]
    eligible = [
        c for c in bf.get_all()
        if hasattr(c, "base_power") and _can_attack(c)
    ]

    if not eligible:
        return

    # Active player chooses which creatures to attack with
    chosen = active.choose(eligible, "declare attackers")

    # Normalize to a list
    if chosen is None:
        return
    if not isinstance(chosen, list):
        chosen = [chosen]

    # Validate and register attackers
    for attacker in chosen:
        if attacker not in eligible:
            continue
        if not _can_attack(attacker):
            continue

        combat.attackers[attacker] = defending
        combat.attacker_blockers[attacker] = []
        attacker.is_attacking = True

        # Tap the attacker unless it has vigilance
        kw = getattr(attacker, "keywords", Keyword(0))
        if Keyword.VIGILANCE not in kw:
            attacker.is_tapped = True


def declare_blockers_step(game: GameState) -> None:
    """Declare blockers step: defending player assigns blockers.

    The defending player is asked (via :meth:`Player.choose`) to assign
    blockers.  The expected format is a dict mapping blocker → attacker
    (or blocker → list of attackers for multi-blocking scenarios), but
    commonly blocker → attacker.

    After blockers are assigned:
    - Menace check: attackers with menace must be blocked by 2+ creatures.
    - Flying/reach check is already handled by ``_can_block``.
    - The attacking player orders blockers for each attacker (for damage
      assignment).

    Parameters:
        game: The current game state.
    """
    combat = game.combat_state

    if not combat.attackers:
        return

    defending = game.non_active_player
    active = game.active_player

    from engine.types import Zone
    bf_defending = defending.zones[Zone.BATTLEFIELD]
    eligible_blockers = [
        c for c in bf_defending.get_all()
        if hasattr(c, "base_power") and not getattr(c, "is_tapped", False)
    ]

    if not eligible_blockers:
        return

    # Defending player chooses block assignments
    # Expected format: dict mapping blocker → attacker (or list of attackers)
    block_assignments = defending.choose(
        eligible_blockers,
        "declare blockers",
    )

    if block_assignments is None:
        return

    if not isinstance(block_assignments, dict):
        return

    # Process block assignments
    for blocker, target in block_assignments.items():
        # Validate that the blocker is in the eligible set
        if blocker not in eligible_blockers:
            continue
        targets = target if isinstance(target, list) else [target]
        valid_targets = []
        max_blocked = getattr(blocker, "_max_attackers_blocked", 1)
        for attacker in targets:
            if len(valid_targets) >= max_blocked:
                break
            if attacker in combat.attackers and _can_block(blocker, attacker):
                valid_targets.append(attacker)
        if valid_targets:
            combat.blockers[blocker] = valid_targets
            blocker.is_blocking = True
            for attacker in valid_targets:
                if attacker not in combat.attacker_blockers:
                    combat.attacker_blockers[attacker] = []
                combat.attacker_blockers[attacker].append(blocker)

    # Menace check: attackers with menace that have fewer than 2 blockers
    # are treated as unblocked (remove the single blocker assignment).
    for attacker, blocker_list in list(combat.attacker_blockers.items()):
        kw = getattr(attacker, "keywords", Keyword(0))
        if Keyword.MENACE in kw and len(blocker_list) < 2 and len(blocker_list) > 0:
            # Illegal block — remove these blockers
            for b in blocker_list:
                if b in combat.blockers:
                    combat.blockers[b] = [
                        a for a in combat.blockers[b] if a is not attacker
                    ]
                    if not combat.blockers[b]:
                        del combat.blockers[b]
                        b.is_blocking = False
            combat.attacker_blockers[attacker] = []

    # Mark attackers that have at least one blocker as "was_blocked".
    # Per MTG rule 509.1h, once a creature is blocked it remains blocked
    # even if all its blockers are removed before the damage step.
    for attacker, blocker_list in combat.attacker_blockers.items():
        if blocker_list:
            combat.was_blocked.add(attacker)

    # Controller of each attacker orders the blockers for damage assignment
    for attacker, blocker_list in combat.attacker_blockers.items():
        if len(blocker_list) > 1:
            controller = getattr(attacker, "controller", active)
            ordered = controller.assign_damage_order(blocker_list)
            combat.attacker_blockers[attacker] = ordered


def combat_damage_step(game: GameState) -> None:
    """Combat damage step: deal combat damage.

    Handles:
    - First strike / double strike creatures deal damage first.
    - State-based actions are checked between first-strike and normal damage.
    - Trample: excess damage over blocker toughness → defending player.
    - Lifelink: controller gains life equal to damage dealt.
    - Deathtouch: any damage is lethal (1 damage = lethal assignment).
    - Unblocked attackers deal damage to defending player.

    Parameters:
        game: The current game state.
    """
    from engine.state_based_actions import resolve_state_based_actions

    combat = game.combat_state

    if not combat.attackers:
        return

    all_attackers = list(combat.attackers.keys())

    # Determine if a first-strike damage sub-step is needed
    # Check both attackers and blockers for first strike / double strike
    all_blockers = set()
    for blocker_list in combat.attacker_blockers.values():
        all_blockers.update(blocker_list)

    has_first_strike_step = any(
        Keyword.FIRST_STRIKE in getattr(c, "keywords", Keyword(0))
        or Keyword.DOUBLE_STRIKE in getattr(c, "keywords", Keyword(0))
        for c in list(all_attackers) + list(all_blockers)
    )

    # --- First strike damage sub-step ---
    if has_first_strike_step:
        _assign_combat_damage(all_attackers, combat, game, is_first_strike=True)
        resolve_state_based_actions(game)

    # --- Normal damage sub-step ---
    _assign_combat_damage(all_attackers, combat, game, is_first_strike=False)
    resolve_state_based_actions(game)


def _assign_combat_damage(
    attackers: list[Any],
    combat: CombatState,
    game: GameState,
    *,
    is_first_strike: bool = False,
) -> None:
    """Assign and deal combat damage for a set of attackers.

    For each attacker:
    - If unblocked → damage to defending player.
    - If blocked → damage assigned to blockers in order.  With trample,
      excess damage goes to the defending player.
    - Blockers deal damage back to the attacker they block.

    When *is_first_strike* is ``True``, only creatures with
    ``FIRST_STRIKE`` or ``DOUBLE_STRIKE`` deal damage (both attackers
    and blockers).  When ``False``, only creatures *without*
    ``FIRST_STRIKE`` deal damage (plus ``DOUBLE_STRIKE`` creatures,
    which participate in both steps).  Blockers that are no longer on
    the battlefield (e.g. killed by first-strike damage and removed by
    SBAs) are skipped.
    """
    from engine.types import Zone

    # Track which blockers have already dealt their damage this sub-step
    # (blockers only deal damage once even if blocking multiple attackers)
    blockers_dealt: set[int] = set()

    for attacker in attackers:
        if attacker not in combat.attackers:
            continue

        kw = getattr(attacker, "keywords", Keyword(0))
        has_first = Keyword.FIRST_STRIKE in kw
        has_double = Keyword.DOUBLE_STRIKE in kw

        # Determine if this attacker deals damage in this sub-step
        if is_first_strike:
            attacker_deals = has_first or has_double
        else:
            attacker_deals = not has_first or has_double

        # Skip if attacker is no longer on the battlefield
        if attacker_deals:
            controller = getattr(attacker, "controller", None)
            if controller is not None:
                bf = controller.zones[Zone.BATTLEFIELD]
                if not bf.contains(attacker):
                    attacker_deals = False

        defending_player = combat.attackers[attacker]
        blocker_list = combat.attacker_blockers.get(attacker, [])
        attacker_kw = getattr(attacker, "keywords", Keyword(0))

        if attacker_deals:
            power = getattr(attacker, "power", 0)

            # Check if attacker was blocked.  Per MTG rule 509.1h, a blocked
            # creature stays blocked even if all its blockers are removed.
            is_blocked = attacker in combat.was_blocked

            if not is_blocked and not blocker_list:
                # Truly unblocked → damage to defending player
                _deal_damage(attacker, defending_player, power, game, combat)
            elif is_blocked and not blocker_list:
                # Was blocked but all blockers removed.
                # Without trample: deals no damage.
                # With trample: all damage tramples to defending player.
                has_trample = Keyword.TRAMPLE in attacker_kw
                if has_trample:
                    _deal_damage(attacker, defending_player, power, game, combat)
                # else: no damage dealt
            else:
                # Blocked → assign damage to blockers in order
                has_trample = Keyword.TRAMPLE in attacker_kw
                remaining_damage = power

                for i, blocker in enumerate(blocker_list):
                    if remaining_damage <= 0:
                        break

                    lethal = _get_lethal_damage(blocker, attacker)

                    if i < len(blocker_list) - 1:
                        # Not the last blocker — assign lethal damage
                        assign = min(lethal, remaining_damage)
                    else:
                        # Last blocker
                        if has_trample:
                            # With trample: assign lethal, rest tramples through
                            assign = min(lethal, remaining_damage)
                        else:
                            # Without trample: all remaining damage to last blocker
                            assign = remaining_damage

                    _deal_damage(attacker, blocker, assign, game, combat)
                    remaining_damage -= assign

                # Trample: excess damage to defending player
                if has_trample and remaining_damage > 0:
                    _deal_damage(attacker, defending_player, remaining_damage, game, combat)

        # Blockers deal damage back to the attacker
        for blocker in blocker_list:
            if id(blocker) not in blockers_dealt:
                blocker_kw = getattr(blocker, "keywords", Keyword(0))
                blocker_has_first = Keyword.FIRST_STRIKE in blocker_kw
                blocker_has_double = Keyword.DOUBLE_STRIKE in blocker_kw

                # Determine if this blocker deals damage in this sub-step
                if is_first_strike:
                    should_deal = blocker_has_first or blocker_has_double
                else:
                    should_deal = not blocker_has_first or blocker_has_double

                # Skip if blocker is no longer on the battlefield
                if should_deal:
                    blocker_ctrl = getattr(blocker, "controller", None)
                    if blocker_ctrl is not None:
                        bf = blocker_ctrl.zones[Zone.BATTLEFIELD]
                        if not bf.contains(blocker):
                            should_deal = False

                if should_deal:
                    blocker_power = getattr(blocker, "power", 0)
                    _deal_damage(blocker, attacker, blocker_power, game, combat)
                    blockers_dealt.add(id(blocker))


def end_combat_step(game: GameState) -> None:
    """End combat step: remove from combat and clear combat state.

    Resets ``is_attacking`` and ``is_blocking`` flags on all creatures
    and clears the combat state.

    Parameters:
        game: The current game state.
    """
    combat = game.combat_state

    # Clear combat flags on all attackers
    for attacker in combat.attackers:
        if hasattr(attacker, "is_attacking"):
            attacker.is_attacking = False

    # Clear combat flags on all blockers
    for blocker in combat.blockers:
        if hasattr(blocker, "is_blocking"):
            blocker.is_blocking = False

    combat.clear()
