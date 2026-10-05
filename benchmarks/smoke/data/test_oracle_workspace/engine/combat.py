"""Combat system: declare attackers → declare blockers → damage → end combat.

Implements the four substeps of the MTG combat phase:

1. **Declare Attackers** — Active player chooses creatures to attack with,
   and what each attacks, through Player Queries.  Attackers are tapped
   (unless they have vigilance).  Creatures with summoning sickness (without
   haste) or the defender keyword cannot attack.

2. **Declare Blockers** — Defending player chooses blockers, and what each
   blocks, through Player Queries.  Creatures with flying can only be blocked
   by creatures with flying or reach.  Creatures with menace require 2+
   blockers.

A declaration is a Player Query like the Priority Query (see ADR-017): the
engine offers every untapped creature the declaring player controls, and a
declaration the rules forbid is rejected with ``InvalidPlayerChoiceError`` and
asked again, never silently trimmed.

3. **Combat Damage** — First strike / double strike creatures deal damage
   first, then state-based actions are checked, then normal damage.  The
   controller of an attacker blocked by two or more creatures divides its
   damage among them through Player Queries.  Trample excess goes to the
   defending player.  Lifelink heals the
   controller.  Deathtouch makes any nonzero damage lethal.  Unblocked
   attackers deal damage to the defending player.

4. **End Combat** — Clear all combat state.

References: MTG Comprehensive Rules §506–§511.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine import attempts
from engine.attempts import AttemptContext
from engine.decisions import Decision, GameRef, InvalidPlayerChoiceError, PlayerDecision
from engine.events import AttacksTriggeredEvent, DealsDamageTriggeredEvent
from engine.queries import (
    DECLARE_ATTACKERS_WINDOW,
    DECLARE_BLOCKERS_WINDOW,
    PlayerQuery,
    ask,
)
from engine.refs_registry import object_options
from engine.types import CardType, Keyword, Zone

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
        attacked_planeswalkers: Mapping of each attacked planeswalker → its
            zone epoch and controller when attackers were declared, so it is
            known to have left combat once either changes (rule 506.4).
        in_combat: Whether the combat phase is currently active.
    """

    attackers: dict[Any, Player] = field(default_factory=dict)
    blockers: dict[Any, list[Any]] = field(default_factory=dict)
    attacker_blockers: dict[Any, list[Any]] = field(default_factory=dict)
    damage_assignments: dict[Any, list[tuple[Any, int]]] = field(default_factory=dict)
    was_blocked: set[Any] = field(default_factory=set)
    attacked_planeswalkers: dict[Any, tuple[int, Any]] = field(default_factory=dict)
    # Attacked planeswalkers that have left combat; they never rejoin it (rule 506.4).
    departed_planeswalkers: list[Any] = field(default_factory=list)
    in_combat: bool = False

    def clear(self) -> None:
        """Reset all combat state."""
        self.attackers.clear()
        self.blockers.clear()
        self.attacker_blockers.clear()
        self.damage_assignments.clear()
        self.was_blocked.clear()
        self.attacked_planeswalkers.clear()
        self.departed_planeswalkers.clear()
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
    - A continuous effect has set ``_cant_be_blocked`` on the attacker
      (e.g. Rogue's Passage).
    - If the attacker has flying, the blocker must have flying or reach.
    """
    if getattr(blocker, "is_tapped", False):
        return False

    # Check for "can't block" restriction (set by continuous effects like Pacifism)
    if getattr(blocker, "_cant_block", False):
        return False

    # Check for "can't be blocked" restriction on the attacker
    if getattr(attacker, "_cant_be_blocked", False):
        return False

    attacker_kw = getattr(attacker, "keywords", Keyword(0))
    blocker_kw = getattr(blocker, "keywords", Keyword(0))

    # Flying check
    if Keyword.FLYING in attacker_kw:
        if Keyword.FLYING not in blocker_kw and Keyword.REACH not in blocker_kw:
            return False

    # Protection check — attacker with protection from blocker can't be blocked
    from engine.protection import has_protection_from

    if has_protection_from(attacker, blocker):
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

    Protection prevents damage from sources with the protected-from quality.
    """
    if amount <= 0:
        return

    # Protection prevents damage (D in DEBT).
    from engine.protection import has_protection_from

    if has_protection_from(target, source):
        return

    # "Prevent all combat damage that would be dealt to it this turn" (rule
    # 615.1): prevented damage is never dealt, so nothing below happens.
    if getattr(target, "combat_damage_prevented", False):
        return

    # Record damage assignment
    if source not in combat_state.damage_assignments:
        combat_state.damage_assignments[source] = []
    combat_state.damage_assignments[source].append((target, amount))

    # Apply damage
    is_damage_recipient = False
    if hasattr(target, "life"):
        # Target is a player
        target.life -= amount
        is_damage_recipient = True
    else:
        # A permanent gets every result of damage that applies to it: a
        # creature-planeswalker loses loyalty and is marked with damage alike.
        if CardType.PLANESWALKER in getattr(target, "card_types", ()):
            # Damage dealt to a planeswalker removes that many loyalty counters (rule 120.3c).
            from engine.game import remove_counter

            remove_counter(game, target, "loyalty", amount)
            is_damage_recipient = True
        if hasattr(target, "damage_marked"):
            # Damage dealt to a creature is marked on it (rule 120.3e).
            target.damage_marked += amount
            is_damage_recipient = True

            # Track deathtouch damage for SBA rule 704.5h
            source_kw_dt = getattr(source, "keywords", Keyword(0))
            if Keyword.DEATHTOUCH in source_kw_dt:
                target.dealt_deathtouch_damage = True

    # Fire the combat-damage trigger (rule 510.2 — after damage is dealt, its
    # triggered abilities go on the stack). ``is_combat``/``combat`` both mark
    # this as combat damage so a subscriber that gates on it (Drake Hatcher's
    # incubation, prowess-of-combat, etc.) fires here but stays dormant for
    # non-combat damage, which fires the same event from engine.game.deal_damage
    # with those flags left False. Fired from the engine's combat site (the sole
    # combat-damage path) — never synthesized from snapshot deltas.
    if is_damage_recipient:
        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=source, target=target, amount=amount,
                is_combat=True, combat=True,
            ),
        )

    # Lifelink: controller gains life equal to damage dealt
    source_kw = getattr(source, "keywords", Keyword(0))
    if Keyword.LIFELINK in source_kw:
        controller = getattr(source, "controller", None)
        if controller is not None:
            from engine.game import gain_life
            gain_life(game, controller, amount)


# ---------------------------------------------------------------------------
# Combat steps
# ---------------------------------------------------------------------------

def _divide_damage(
    game: GameState, attacker: Any, blockers: list[Any], power: int, trample: bool
) -> tuple[list[tuple[Any, int]], int]:
    """How the controller of *attacker*, blocked by two or more creatures,
    divides its *power* combat damage among *blockers* (rule 510.1c); return
    each blocker's share and, with trample, what is left for the player or
    planeswalker it attacks (rule 702.19c).

    Each blocker in turn is a NUMBER Player Query sourced by the attacker,
    with that blocker's OBJECT decision as its question payload: how much of
    the damage still undivided it is assigned. Without trample the last
    blocker is assigned the rest unasked. A division the rules forbid —
    damage left over while a blocker is assigned less than lethal damage — is
    rejected and the division asked again (an explicit attempt, see ADR-017).
    """
    controller = getattr(attacker, "controller", None) or game.active_player
    asked = blockers if trample else blockers[:-1]

    def divide() -> tuple[list[tuple[Any, int]], int]:
        remaining = power
        division: list[tuple[Any, int]] = []
        for blocker in asked:
            amount = _choose_share(game, controller, attacker, blocker, remaining)
            division.append((blocker, amount))
            remaining -= amount
        if not trample:
            division.append((blockers[-1], remaining))
            remaining = 0
        if remaining and any(amount < _get_lethal_damage(b, attacker) for b, amount in division):
            raise InvalidPlayerChoiceError(
                f"{getattr(attacker, 'name', attacker)!r} can't assign trample damage "
                "past a blocker assigned less than lethal damage"
            )
        return division, remaining

    return attempts.attempt(game, divide)


def _choose_share(game: GameState, controller: Any, attacker: Any, blocker: Any, remaining: int) -> int:
    """Ask how much of *attacker*'s *remaining* damage *blocker* is assigned."""
    (blocker_option,), _ = object_options(game.refs, _battlefield_items(game, [blocker]))
    query = PlayerQuery(
        source=(_object_source(game, attacker),),
        prompt=(
            f"assign {getattr(attacker, 'name', 'the attacker')}'s combat damage: "
            f"how much of {remaining} to {getattr(blocker, 'name', 'this blocker')}"
        ),
        options=tuple(Decision.number(n) for n in range(remaining + 1)),
        min=1,
        max=1,
        question=(blocker_option,),
    )
    return dict(ask(controller, query).selected[0].attrs)["value"]


def _battlefield_items(game: GameState, objs: list[Any]) -> list[tuple[Any, str, int | None]]:
    return [
        (obj, Zone.BATTLEFIELD.value, game.refs.seat_of(getattr(obj, "controller", None)))
        for obj in objs
    ]


def _object_source(game: GameState, obj: Any) -> PlayerDecision:
    return game.refs.object_decision(
        obj,
        zone=Zone.BATTLEFIELD.value,
        controller_seat=game.refs.seat_of(getattr(obj, "controller", None)),
    )


def _declaration_outcome(
    game: GameState, declaration: dict[Any, Any], chosen: dict[int, PlayerDecision]
) -> tuple[tuple[PlayerDecision, tuple[PlayerDecision, ...]], ...]:
    """The declaration as decisions: each declared creature's option with the
    defender it attacks, or the attackers it blocks."""
    outcome = []
    for creature, targets in declaration.items():
        targets = targets if isinstance(targets, list) else [targets]
        decisions = tuple(
            game.refs.player_decision(t, seat=game.refs.seat_of(t)) if hasattr(t, "life")
            else object_options(game.refs, _battlefield_items(game, [t]))[0][0]
            for t in targets
        )
        outcome.append((chosen[id(creature)], decisions))
    return tuple(outcome)


def _declaration_source(game: GameState, player: Player, window: tuple[str, str]) -> PlayerDecision:
    seat = game.refs.seat_of(player)
    return Decision.player(
        ref=GameRef(player=frozenset({("seat", seat)}), ability=frozenset({window})),
        seat=seat,
        name=player.name,
    )


def _untapped_creatures(player: Player) -> list[Any]:
    return [
        c for c in player.zones[Zone.BATTLEFIELD].get_all()
        if hasattr(c, "base_power") and not getattr(c, "is_tapped", False)
    ]


def _declare(
    game: GameState,
    context: AttemptContext,
    player: Player,
    window: tuple[str, str],
    prompt: str,
    candidates: list[Any],
    follow_up: Callable[[list[Any]], Any],
) -> Any:
    """Ask *player* for a declaration until they give one the rules allow.

    The declaration query is a multi-select of OBJECT options for
    *candidates* — asked even when there are none, since the declaration
    still happens; declining declares nothing. ``follow_up(chosen)`` asks the
    per-creature questions and returns the declaration, raising
    ``InvalidPlayerChoiceError`` when the rules forbid it. Once every question
    is answered, :meth:`~engine.player.Player.confirm_declaration` shows the
    player the declaration that would take effect — each declared creature
    with what it attacks or blocks — and lets them withdraw it first.

    The declaration is an attempt (:mod:`engine.attempts`) whose rejection
    boundary is its own start: a rejected declaration is rolled back there, the
    owner of the rejection hears it through
    :meth:`~engine.player.Player.on_attempt_rejected`, and the same
    declaration is asked again (CR 733.2, see ADR-017). ``context`` is the
    declaration's attempt, which the caller ends.
    """
    with attempts.active(context):
        while True:
            context.begin_try()
            options, by_decision = object_options(game.refs, _battlefield_items(game, candidates))
            query = PlayerQuery(
                source=(_declaration_source(game, player, window),),
                prompt=prompt,
                options=options,
                min=0,
                max=len(options),
            )
            answer = ask(player, query)
            context.query, context.answer = query, answer
            try:
                declaration = follow_up([by_decision[d] for d in answer.selected])
                chosen = {id(by_decision[d]): d for d in answer.selected}
                player.confirm_declaration(
                    query, answer, _declaration_outcome(game, declaration, chosen)
                )
            except InvalidPlayerChoiceError as error:
                context.boundary.restore()
                context.reject(error)
                # What the hook changed outside its rollback-exempt state is
                # not part of what follows (see Player.on_attempt_rejected).
                context.boundary.restore()
                continue
            context.taken, context.result = True, declaration
            return declaration


def declare_attackers_step(game: GameState) -> None:
    """Declare attackers step: the active player declares attackers.

    The active player is asked which creatures attack — a multi-select of
    OBJECT options for every untapped creature they control, declining to
    attack with none — and then what each attacker attacks: the defending
    player (a PLAYER option) or a planeswalker they control (OBJECT options),
    asked even when the defending player is the only choice. The declaration's
    source is the active player's PLAYER decision carrying
    :data:`~engine.queries.DECLARE_ATTACKERS_WINDOW`; each follow-up question
    is sourced by the attacking creature's OBJECT decision.

    A declaration naming a creature that can't attack is rejected and asked
    again. Each registered attacker is tapped (unless it has vigilance) and
    its ``is_attacking`` flag is set.
    """
    combat = game.combat_state
    combat.in_combat = True
    active = game.active_player
    defending = game.non_active_player

    candidates = _untapped_creatures(active)

    def follow_up(chosen: list[Any]) -> dict[Any, Any]:
        for creature in chosen:
            if not _can_attack(creature):
                raise InvalidPlayerChoiceError(
                    f"{getattr(creature, 'name', creature)!r} can't attack"
                )
        return {creature: _choose_defender(game, active, defending, creature) for creature in chosen}

    context = AttemptContext(game, "declaration", actor=active)
    try:
        attacks = _declare(
            game, context, active, DECLARE_ATTACKERS_WINDOW, "declare attackers",
            candidates, follow_up,
        )
        _register_attacks(game, attacks)
    finally:
        # Registered or ended by an error: the declaration is over.
        active.on_action_ended(context)


def _register_attacks(game: GameState, attacks: dict) -> None:
    combat = game.combat_state
    defending = game.non_active_player
    declared: list[Any] = []
    for attacker, defender in attacks.items():
        if defender is not defending:
            combat.attacked_planeswalkers[defender] = (
                game.refs.zone_epoch(defender),
                getattr(defender, "controller", None),
            )
        combat.attackers[attacker] = defender
        combat.attacker_blockers[attacker] = []
        attacker.is_attacking = True
        declared.append(attacker)

        # Tap the attacker unless it has vigilance
        kw = getattr(attacker, "keywords", Keyword(0))
        if Keyword.VIGILANCE not in kw:
            attacker.is_tapped = True

    # Raid and similar abilities ask whether a player attacked this turn: a
    # player has attacked once they declare at least one attacker (rule 508.1).
    if declared:
        game.active_player.attacked_this_turn = True

    # All attackers are declared simultaneously (rule 508.1); only after the
    # whole set is registered do "whenever ~ attacks" abilities go on the stack
    # (rule 508.2), so a trigger reading "each other attacking creature"
    # (Dauntless Veteran) sees the complete set. Fire once per attacker in
    # declaration order (APNAP within the active player = registration order).
    for attacker in declared:
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=attacker, attacker=attacker)
        )


def _choose_defender(game: GameState, active: Player, defending: Player, attacker: Any) -> Any:
    """What *attacker* attacks: the defending player, or a planeswalker they
    control (rule 508.1b). Always asked, even when the defending player is the
    only choice, so the answer names the defender the attack really has."""
    planeswalkers = [
        p for p in defending.zones[Zone.BATTLEFIELD].get_all()
        if CardType.PLANESWALKER in getattr(p, "card_types", ())
    ]
    player_option = game.refs.player_decision(defending, seat=game.refs.seat_of(defending))
    walker_options, by_decision = object_options(game.refs, _battlefield_items(game, planeswalkers))
    query = PlayerQuery(
        source=(_object_source(game, attacker),),
        prompt=f"choose what {getattr(attacker, 'name', 'the attacker')} attacks",
        options=(player_option, *walker_options),
        min=1,
        max=1,
    )
    choice = ask(active, query).selected[0]
    return defending if choice == player_option else by_decision[choice]


def declare_blockers_step(game: GameState) -> None:
    """Declare blockers step: the defending player declares blockers.

    The defending player is asked which creatures block — a multi-select of
    OBJECT options for every untapped creature they control, declining to
    block with none — and then, for each chosen blocker, which attackers it
    blocks: OBJECT options for the attacking creatures, choosing at least one
    and at most as many as the blocker may block. The declaration's source is
    the defending player's PLAYER decision carrying
    :data:`~engine.queries.DECLARE_BLOCKERS_WINDOW`; each follow-up question
    is sourced by the blocking creature's OBJECT decision.

    A declaration the rules forbid — a blocker that can't block the attacker
    it names (evasion, "can't block", protection), more attackers than the
    blocker may block, or a menace attacker blocked by a single creature — is
    rejected and asked again.
    """
    combat = game.combat_state

    if not combat.attackers:
        return

    defending = game.non_active_player
    candidates = _untapped_creatures(defending)

    def follow_up(chosen: list[Any]) -> dict[Any, list[Any]]:
        blocks = {blocker: _choose_blocked(game, defending, blocker) for blocker in chosen}
        _check_blocks(blocks)
        return blocks

    context = AttemptContext(game, "declaration", actor=defending)
    try:
        blocks = _declare(
            game, context, defending, DECLARE_BLOCKERS_WINDOW, "declare blockers",
            candidates, follow_up,
        )
        _register_blocks(game, blocks)
    finally:
        # Registered or ended by an error: the declaration is over.
        defending.on_action_ended(context)


def _register_blocks(game: GameState, blocks: dict) -> None:
    combat = game.combat_state
    for blocker, blocked in blocks.items():
        combat.blockers[blocker] = blocked
        blocker.is_blocking = True
        for attacker in blocked:
            combat.attacker_blockers.setdefault(attacker, []).append(blocker)

    # Mark attackers that have at least one blocker as "was_blocked".
    # Per MTG rule 509.1h, once a creature is blocked it remains blocked
    # even if all its blockers are removed before the damage step.
    for attacker, blocker_list in combat.attacker_blockers.items():
        if blocker_list:
            combat.was_blocked.add(attacker)



def _choose_blocked(game: GameState, defending: Player, blocker: Any) -> list[Any]:
    """Ask which attackers *blocker* blocks."""
    attackers = list(game.combat_state.attackers)
    options, by_decision = object_options(game.refs, _battlefield_items(game, attackers))
    query = PlayerQuery(
        source=(_object_source(game, blocker),),
        prompt=f"choose what {getattr(blocker, 'name', 'the blocker')} blocks",
        options=options,
        min=1,
        max=min(len(options), max(1, getattr(blocker, "_max_attackers_blocked", 1))),
    )
    return [by_decision[d] for d in ask(defending, query).selected]


def _check_blocks(blocks: dict[Any, list[Any]]) -> None:
    """Raise ``InvalidPlayerChoiceError`` unless the rules allow *blocks*."""
    blockers_of: dict[Any, list[Any]] = {}
    for blocker, blocked in blocks.items():
        for attacker in blocked:
            if not _can_block(blocker, attacker):
                raise InvalidPlayerChoiceError(
                    f"{getattr(blocker, 'name', blocker)!r} can't block "
                    f"{getattr(attacker, 'name', attacker)!r}"
                )
            blockers_of.setdefault(attacker, []).append(blocker)
    for attacker, blockers in blockers_of.items():
        if Keyword.MENACE in getattr(attacker, "keywords", Keyword(0)) and len(blockers) < 2:
            raise InvalidPlayerChoiceError(
                f"{getattr(attacker, 'name', attacker)!r} has menace and can't be "
                "blocked except by two or more creatures"
            )


def combat_damage_step(game: GameState, *, sub_step: str | None = None) -> None:
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
        sub_step: ``None`` (default) runs the full step — a first-strike
            pass when any combatant has first/double strike, then the
            normal pass. ``"first_strike"`` or ``"normal"`` runs only that
            pass, for callers that walk the two damage steps separately
            (e.g. replay validation following the GRE step sequence).
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
    if sub_step in (None, "first_strike") and has_first_strike_step:
        _assign_combat_damage(all_attackers, combat, game, is_first_strike=True)
        resolve_state_based_actions(game)

    # --- Normal damage sub-step ---
    if sub_step in (None, "normal"):
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

        defending_player = _attacked(game, combat, attacker)
        blocker_list = combat.attacker_blockers.get(attacker, [])
        attacker_kw = getattr(attacker, "keywords", Keyword(0))

        if attacker_deals:
            power = getattr(attacker, "power", 0)

            # Check if attacker was blocked.  Per MTG rule 509.1h, a blocked
            # creature stays blocked even if all its blockers are removed.
            is_blocked = attacker in combat.was_blocked

            if not is_blocked and not blocker_list:
                # Truly unblocked → damage to defending player
                if defending_player is not None:
                    _deal_damage(attacker, defending_player, power, game, combat)
            elif is_blocked and not blocker_list:
                # Was blocked but all blockers removed.
                # Without trample: deals no damage.
                # With trample: all damage tramples to defending player.
                has_trample = Keyword.TRAMPLE in attacker_kw
                if has_trample and defending_player is not None:
                    _deal_damage(attacker, defending_player, power, game, combat)
                # else: no damage dealt
            else:
                has_trample = Keyword.TRAMPLE in attacker_kw
                if len(blocker_list) > 1:
                    division, remaining_damage = _divide_damage(
                        game, attacker, blocker_list, power, has_trample
                    )
                else:
                    # One blocker: lethal to it, and with trample the rest
                    # tramples over; without trample, all of it.
                    (blocker,) = blocker_list
                    share = min(_get_lethal_damage(blocker, attacker), power) if has_trample else power
                    division, remaining_damage = [(blocker, share)], power - share

                for blocker, assign in division:
                    if assign > 0:
                        _deal_damage(attacker, blocker, assign, game, combat)

                # Trample: excess damage to defending player
                if has_trample and remaining_damage > 0 and defending_player is not None:
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


def _attacked(game: GameState, combat: CombatState, attacker: Any) -> Any:
    """What *attacker* is attacking — ``None`` once the planeswalker it attacks
    has left combat by changing zones, controller or card type (rule 506.4).

    The attacker stays attacking and blockable, but deals no combat damage to
    the departed planeswalker or anyone in its place (rules 506.4c, 510.1b).
    """
    defender = combat.attackers[attacker]
    if defender not in combat.attacked_planeswalkers:
        return defender
    note_planeswalker_departures(game)
    return None if any(d is defender for d in combat.departed_planeswalkers) else defender


def note_planeswalker_departures(game: GameState) -> None:
    """Record each attacked planeswalker that has left combat — by changing
    zones, controller or card type since attackers were declared (rule 506.4).

    Called whenever the game settles, on its settled characteristics, and
    before combat damage. A recorded departure is permanent for this combat:
    regaining the controller or type does not rejoin it.
    """
    combat = getattr(game, "combat_state", None)
    if combat is None:
        return
    for defender, (epoch, controller) in combat.attacked_planeswalkers.items():
        if any(d is defender for d in combat.departed_planeswalkers):
            continue
        if (
            game.refs.zone_epoch(defender) != epoch
            or getattr(defender, "controller", None) is not controller
            or CardType.PLANESWALKER not in getattr(defender, "card_types", ())
        ):
            combat.departed_planeswalkers.append(defender)


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
