"""Test utility helpers for engine validation and benchmark agents.

Provides convenience functions for setting up game states, casting spells,
advancing phases, and managing combat in tests.  Each function raises
descriptive errors on failure.

Play is driven through Priority Queries (ADR-017): a test gives each player an
ordered action script (:func:`script` with :func:`act`, :func:`act_illegal` and
:func:`pass_priority` entries) and drives it with :func:`run_scripts`; the
engine, not the test, performs each chosen cast, land play or activation. The
casting and activation helpers are one-entry scripts. A rejected action or
choice is retried only with the next of the test's explicit branches
(``act(branches=[...])``, ``Intent(branches=[...])``).

Functions:
    create_game — convenience wrapper to create a GameState from card lists.
    set_board_state — directly set zone contents and player state.
    script / run_scripts — give players action scripts and play them out.
    cast_spell — find card in hand by name, cast it through priority, and resolve.
    advance_to_phase — fast-forward game state to a given phase/step.
    declare_attackers — advance to combat and declare attackers by name.
    declare_blockers — assign blockers by name mapping.
"""

from __future__ import annotations

from typing import Any

from engine.abilities import AbilityError
from engine.card import CardImpl
from engine.casting import CastingError
from engine.combat import (
    declare_attackers_step,
    declare_blockers_step,
)
from engine.decisions import Decision, GameRef
from engine.game import create_game as _engine_create_game
from engine.game_state import _TURN_SEQUENCE, GameState
from engine.intent_player import (  # noqa: F401 — script entries are re-exported for tests
    DeterministicPlayer,
    Intent,
    ScriptEntry,
    ScriptEntryError,
    act,
    act_illegal,
    branch,
    pass_priority,
)
from engine.stack import resolve_top_of_stack
from engine.types import ManaType, Phase, Step, Zone


class TestSetupError(Exception):
    """Raised when a test utility function encounters an invalid setup."""


def card_colors(card: Any) -> set[str]:
    """Return a card's colors as single-letter strings, derived from its mana cost.

    Hybrid pips contribute both options. {C} and {X} contribute nothing.
    Returns an empty set for cards with no mana cost or only colorless/X pips.
    """
    colors: set[str] = set()
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return colors
    for mt in getattr(cost, "pips", {}):
        if mt != ManaType.COLORLESS:
            colors.add(mt.value)
    for hybrid in getattr(cost, "hybrid", []):
        if hybrid.option_a != ManaType.COLORLESS:
            colors.add(hybrid.option_a.value)
        if hybrid.option_b != ManaType.COLORLESS:
            colors.add(hybrid.option_b.value)
    return colors


# ---------------------------------------------------------------------------
# create_game
# ---------------------------------------------------------------------------


def create_game(
    deck1: list[CardImpl] | None = None,
    deck2: list[CardImpl] | None = None,
    *,
    player1_name: str = "Player1",
    player2_name: str = "Player2",
    player1_life: int = 20,
    player2_life: int = 20,
) -> GameState:
    """Create a new two-player game from card lists.

    This is a convenience wrapper around :func:`engine.game.create_game`
    that automatically creates intent-based :class:`DeterministicPlayer`
    instances. Choices are answered through Intents the test starts on the
    players (see :class:`engine.intent_player.Intent`), not a positional script.

    Parameters:
        deck1: Cards for player 1's deck.  Defaults to empty list.
        deck2: Cards for player 2's deck.  Defaults to empty list.
        player1_name: Display name for player 1.
        player2_name: Display name for player 2.
        player1_life: Starting life for player 1.
        player2_life: Starting life for player 2.

    Returns:
        A fully initialised :class:`GameState`.

    Raises:
        TestSetupError: If the inputs are invalid.
    """
    if deck1 is None:
        deck1 = []
    if deck2 is None:
        deck2 = []

    p1 = DeterministicPlayer(player1_name, life=player1_life)
    p2 = DeterministicPlayer(player2_name, life=player2_life)

    game = _engine_create_game(p1, p2, deck1, deck2)
    # Let end_intent postconditions read the game without an explicit arg.
    for player in game.players:
        player.game = game

    # When decks are empty (the convenience default), engine.game.create_game
    # attempts to draw 7 cards from each empty library, which sets the
    # drawn_from_empty_library loss flag.  Reset it for the convenience case.
    for player in game.players:
        if player.drawn_from_empty_library:
            player.drawn_from_empty_library = False

    # engine.game.create_game hardcodes life=20; restore custom values.
    if player1_life != 20:
        game.players[0].life = player1_life
    if player2_life != 20:
        game.players[1].life = player2_life

    return game


# ---------------------------------------------------------------------------
# set_board_state
# ---------------------------------------------------------------------------


def set_board_state(
    game: GameState,
    player_index: int,
    *,
    battlefield: list[Any] | None = None,
    hand: list[Any] | None = None,
    graveyard: list[Any] | None = None,
    life: int | None = None,
    mana: dict[ManaType, int] | None = None,
) -> None:
    """Directly set zone contents and player state for test setup.

    Replaces the contents of the specified zones (only zones that are
    explicitly provided are modified — others are left unchanged).

    For each card placed into a zone, ``owner`` and ``controller`` are
    set to the target player.

    Parameters:
        game: The game state to modify.
        player_index: Index of the player (0 or 1).
        battlefield: Cards/permanents to place on the battlefield.
        hand: Cards to place in hand.
        graveyard: Cards to place in graveyard.
        life: Life total to set (or ``None`` to leave unchanged).
        mana: Mana to add to the player's pool.  Keys are
            :class:`ManaType`, values are amounts.

    Raises:
        TestSetupError: If ``player_index`` is out of range.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players (indices 0–{len(game.players) - 1})"
        )

    player = game.players[player_index]

    if life is not None:
        player.life = life

    if mana is not None:
        player.mana_pool.empty()
        for mana_type, amount in mana.items():
            player.mana_pool.add(mana_type, amount)

    if battlefield is not None:
        _set_zone(game, player, Zone.BATTLEFIELD, battlefield)

    if hand is not None:
        _set_zone(game, player, Zone.HAND, hand)

    if graveyard is not None:
        _set_zone(game, player, Zone.GRAVEYARD, graveyard)


def _set_zone(
    game: GameState,
    player: Any,
    zone: Zone,
    cards: list[Any],
) -> None:
    """Replace a zone's contents with *cards*, assigning ownership.

    Each placed object is given a stable engine-minted ``instance_id`` (for the
    zone it is placed in) so a test can reference it in an Intent preference —
    e.g. ``Decision.obj(instance=bear.instance_id)``.
    """
    zone_container = player.zones[zone]
    # Clear existing contents
    for obj in zone_container.get_all():
        zone_container.remove(obj)

    # Add new contents
    for card in cards:
        card.owner = player
        card.controller = player
        zone_container.add(card)
        card.instance_id = game.refs.instance_id(card, zone.value)


# ---------------------------------------------------------------------------
# cast_spell
# ---------------------------------------------------------------------------


def cast_spell(
    game: GameState,
    player_index: int,
    card_name: str,
    targets: list[Any] | None = None,
) -> None:
    """Find a card in hand by name, cast it, and pass priority until resolved.

    The function:
    1. Locates the first card matching *card_name* in the player's hand.
    2. Sets up the game phase/priority for sorcery-speed casting if needed.
    3. Casts it as a one-entry :func:`act` script: the player chooses the card
       in a Priority Query and the engine casts it.
    4. Passes priority for both players so the spell resolves.

    Parameters:
        game: The game state.
        player_index: Index of the casting player (0 or 1).
        card_name: Name of the card to find in hand.
        targets: Optional list of game objects/players to prefer for the
            target Player Query the engine raises during casting.  When
            provided, a transient Intent is started on the casting player
            that prefers each target by its engine-minted ``instance_id``
            (objects) or seat (players); the intent is ended after
            casting in a ``finally`` so it does not leak across calls.

    Raises:
        TestSetupError: If the card is not found in hand or casting fails.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has {len(game.players)} players"
        )

    player = game.players[player_index]
    hand = game.get_hand(player)

    # Find the card by name
    card = None
    for obj in hand.get_all():
        if getattr(obj, "name", None) == card_name:
            card = obj
            break

    if card is None:
        hand_names = [getattr(c, "name", repr(c)) for c in hand.get_all()]
        raise TestSetupError(
            f"Card {card_name!r} not found in player {player_index}'s hand. "
            f"Hand contains: {hand_names}"
        )

    # Ensure sorcery-speed timing for non-instant spells
    from engine.types import CardType, Keyword

    is_instant = CardType.INSTANT in getattr(card, "card_types", set())
    has_flash = Keyword.FLASH in getattr(card, "keywords", Keyword(0))

    if not is_instant and not has_flash:
        # Set up sorcery-speed timing: active player, main phase, empty stack
        game.active_player_index = player_index
        game.priority_player_index = player_index
        if game.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
            game.phase = Phase.PRECOMBAT_MAIN
            game.step = None

    # Ensure the stack is empty for sorcery-speed
    if not game.stack.is_empty():
        raise TestSetupError(f"Cannot cast {card_name!r} — stack is not empty")

    # Targets are chosen via a transient Intent: the engine raises a target
    # Player Query during casting; the intent prefers the given targets by their
    # engine-minted instance id (objects) or seat (players).
    intent_name: str | None = None
    if targets and isinstance(player, DeterministicPlayer):
        prefs = tuple(_target_preference(game, t) for t in targets)
        intent_name = f"_cast_{card_name}"
        player.start_intent(
            intent_name,
            Intent(
                pattern=GameRef(card=frozenset({("name", card_name)})),
                preferences=prefs,
            ),
        )

    try:
        _take_action(game, player, act(_hand_preference(game, card)))
    except ScriptEntryError as exc:
        reason = _rejection_cause(exc) or f"it is not offered at priority ({exc})"
        raise TestSetupError(f"Failed to cast {card_name!r}: {reason}") from exc
    except Exception as exc:
        raise TestSetupError(f"Failed to cast {card_name!r}: {exc}") from exc
    finally:
        if intent_name is not None and intent_name in player._intents:
            player.end_intent(intent_name)

    # Pass priority for both players to resolve the spell
    resolve_stack(game)


def _target_preference(game: GameState, target: Any) -> Any:
    """Build an Intent preference selecting *target* (a game object or player)."""
    seat = game.refs.seat_of(target)
    if seat is not None:
        return Decision.player(seat=seat)
    instance_id = getattr(target, "instance_id", None)
    if instance_id is None:
        # Best effort: mint for the battlefield (the common targeting zone).
        instance_id = game.refs.instance_id(target, "battlefield")
    return Decision.obj(instance=instance_id)


# ---------------------------------------------------------------------------
# Action scripts (ADR-017)
# ---------------------------------------------------------------------------


def script(game: GameState, player_index: int, *entries: ScriptEntry) -> None:
    """Give player ``player_index`` an ordered action script, replacing any
    entries left from an earlier one.

    Each Priority Query the player receives consumes the next entry:
    :func:`act` (an action that must take effect), :func:`act_illegal` (one the
    rules forbid) or :func:`pass_priority`. Preferences name predefined classes
    or Player Decisions, e.g. ``act(GleamOfDeath, GlamdringFoehammer)`` or
    ``act(Decision.ability(printed=LlanowarElvesAbility1))``.
    """
    _deterministic(game, game.players[player_index]).set_script(entries)


def run_scripts(game: GameState, *, max_priority: int = 1000) -> None:
    """Play until every player's script is consumed, leaving the stack in place.

    Priority starts with ``game.priority_player_index`` and moves as in a real
    game: a player who acts keeps priority, two passes in a row resolve the top
    of the stack (the active player then receives priority) or, on an empty
    stack, move the game to the next step that grants priority. A player whose
    script is dry passes.

    The priority round is kept with the game (``game.priority_player_index``
    and ``game.priority_passes``), so a later call carries on from where the
    scripts ran out — with a pending resolution or step change made first if
    both players had passed. The engine starts a fresh round whenever an
    action is taken, an object resolves or the game moves to another step, and
    :func:`resolve_stack` always starts one.

    Rejections follow the engine's attempts (:mod:`engine.attempts`): a
    rejected priority action is retried within its entry, and a rejected choice
    while an object resolves is retried from before that choice — each with
    the next branch of the entry or intent that owns the rejection. Under a
    negative Intent (see :class:`~engine.intent_player.Intent`) a rejection
    counts as a pass, and a resolution-time one stops play there.

    Raises:
        ScriptEntryError: When an entry's action does not go as it requires.
        PostconditionError: When a rejected choice's intent has no branch left, or a
            negative intent's forbidden choice takes effect.
        TestSetupError: If the scripts are not consumed within ``max_priority``
            grants of priority.
    """
    from engine.priority import take_priority

    grants = 0
    while True:
        if not _scripts_remain(game):
            return
        if game.priority_passes >= 2:
            if not game.stack.is_empty():
                if not resolve_top_of_stack(game):
                    return
            elif not _cleanup_grants_priority(game):
                _enter_next_priority_step(game)
            continue
        if grants == max_priority:
            raise TestSetupError(f"scripts not consumed within {max_priority} grants of priority")
        grants += 1
        current = game.priority_player_index
        if take_priority(game, game.players[current]):
            game.priority_passes += 1
            game.priority_player_index = 1 - current


def _scripts_remain(game: GameState) -> bool:
    return any(isinstance(p, DeterministicPlayer) and p.pending_entries for p in game.players)


def _enter_next_priority_step(game: GameState) -> None:
    """Advance to the next step where players receive priority: one outside
    the untap and cleanup steps, or a cleanup step whose actions grant
    priority (rule 514.3a)."""
    from engine.turn import _NO_PRIORITY_STEPS

    while True:
        _enter_next_step(game, finish_cleanup_step=False)
        if game.step == Step.CLEANUP:
            if _cleanup_grants_priority(game):
                return
        elif (game.phase, game.step) not in _NO_PRIORITY_STEPS:
            return


def _cleanup_grants_priority(game: GameState) -> bool:
    """In a cleanup step, perform another cleanup iteration; return whether it
    grants priority, in a fresh round. Outside cleanup, ``False``."""
    from engine.turn import cleanup_iteration

    if game.step != Step.CLEANUP or not cleanup_iteration(game):
        return False
    game.start_priority_round()
    return True


def _deterministic(game: GameState, player: Any) -> DeterministicPlayer:
    if not isinstance(player, DeterministicPlayer):
        raise TestSetupError(f"{player!r} is not a DeterministicPlayer and has no action script")
    return player


def _take_action(game: GameState, player: Any, entry: ScriptEntry) -> Any:
    """Give *player* priority once with *entry* as their whole script; return
    what the engine's action returned. Their own script is left untouched."""
    from engine.priority import take_priority

    player = _deterministic(game, player)
    game.priority_player_index = game.players.index(player)
    saved = player.set_script([entry])
    player.last_action_result = None
    try:
        take_priority(game, player)
    finally:
        player.set_script(saved)
    return player.last_action_result


def _rejection_cause(error: ScriptEntryError) -> BaseException | None:
    """The engine error behind a rejected entry, if it was rejected."""
    if error.error is None:
        return None
    return error.error.__cause__ or error.error


def _hand_preference(game: GameState, card: Any) -> Any:
    return Decision.obj(instance=game.refs.instance_id(card, Zone.HAND.value))


def _ability_preference(game: GameState, source: Any, index: int) -> Any:
    return Decision.ability(
        source=game.refs.instance_id(source, Zone.BATTLEFIELD.value), index=index
    )


def _activate(game: GameState, player: Any, source: Any, index: int) -> Any:
    try:
        return _take_action(game, player, act(_ability_preference(game, source, index)))
    except ScriptEntryError as exc:
        cause = _rejection_cause(exc)
        if cause is not None:
            raise cause
        raise AbilityError(
            f"{getattr(source, 'name', source)!r} ability {index} cannot be activated now"
        ) from exc


def _cast(game: GameState, player: Any, card: Any) -> Any:
    try:
        return _take_action(game, player, act(_hand_preference(game, card)))
    except ScriptEntryError as exc:
        cause = _rejection_cause(exc)
        if cause is not None:
            raise cause
        raise CastingError(f"{getattr(card, 'name', card)!r} cannot be cast now") from exc


def put_on_battlefield(game: GameState, player: Any, card: Any) -> Any:
    """Place a single *card* on *player*'s battlefield; return it.

    The card is given a stable engine-minted ``instance_id`` so a test can
    reference it in an Intent preference (``Decision.obj(instance=card.instance_id)``).
    """
    bf = player.zones[Zone.BATTLEFIELD]
    card.owner = player
    card.controller = player
    bf.add(card)
    card.instance_id = game.refs.instance_id(card, Zone.BATTLEFIELD.value)
    return card


def resolve_stack(game: GameState) -> None:
    """Resolve the entire stack with every player passing; consumes no script
    entries.

    Each resolution is the engine's own (:func:`~engine.stack.resolve_top_of_stack`),
    exactly as in :func:`~engine.stack.priority_loop`: a choice the engine
    rejects while an object resolves is retried from before that choice, with
    the owning intent's next branch; under a negative
    Intent the rejection counts as a pass and resolution stops there. The
    active player then holds priority in a fresh round, even when the stack
    was already empty.

    In a cleanup step's priority window the cleanup step is then finished
    too, with every player passing (:func:`finish_cleanup`): another cleanup
    follows the window, and so on until one grants no priority (CR 514.3a).
    """
    _finish_forced(game)


def _finish_forced(game: GameState) -> bool:
    """Resolve the stack with every player passing and, in a cleanup step,
    finish the cleanup; return ``False`` if a resolution was abandoned, which
    stops play there."""
    if not _drain_stack(game):
        return False
    return game.step != Step.CLEANUP or _finish_cleanup(game)


def _drain_stack(game: GameState) -> bool:
    """Resolve the stack with every player passing, in a fresh round; return
    ``False`` if a resolution was abandoned and stopped there."""
    game.start_priority_round()
    while not game.stack.is_empty():
        if not resolve_top_of_stack(game):
            return False
    return True


def card_abilities(card: Any) -> list:
    """``card``'s activated abilities, followed by any mana abilities it lists
    only in ``get_mana_abilities()``, so either placement of a mana ability
    can be activated by index."""
    abilities = list(card.get_activated_abilities())
    mana = getattr(card, "get_mana_abilities", lambda: [])()
    return abilities + [ability for ability in mana if not any(ability is a for a in abilities)]


def activate_card_ability(
    game: GameState,
    player: Any,
    source_card: Any,
    index: int = 0,
) -> None:
    """Activate ability ``index`` of :func:`card_abilities` (``source_card``'s
    activated abilities, then its other mana abilities) as a one-entry
    :func:`act` script: *player* chooses the ability in a Priority Query and
    the engine activates it — choosing targets **before** paying costs and
    putting it on the stack (a mana ability resolves at once). The caller
    resolves the stack afterward (e.g. via :func:`resolve_stack`) to run the
    ability's effect.

    Raises :class:`~engine.abilities.AbilityError` when the ability is not
    offered or the engine rejects it (no legal target, unmet timing, or
    unpayable cost) — the rejected activation is rolled back, so no cost is
    spent.
    """
    _activate(game, player, source_card, index)


def activate_loyalty_ability(
    game: GameState,
    player: Any,
    source_card: Any,
    index: int = 0,
) -> None:
    """Activate ``source_card``'s loyalty ability ``index`` as a one-entry
    :func:`act` script: *player* chooses it in a Priority Query (offered only
    at sorcery speed and once per turn) and the engine activates it, choosing
    targets **before** paying the loyalty cost. The caller resolves the stack
    afterward (e.g. via :func:`resolve_stack`) to run the ability's effect.

    Raises :class:`~engine.abilities.AbilityError` when the ability is not
    offered or the engine rejects it (wrong timing, already activated this
    turn, insufficient loyalty, or a required target with no legal choice) —
    no loyalty is spent in that case.
    """
    from engine.priority import activatable_abilities

    loyalty_offset = len(activatable_abilities(source_card, game)) - len(
        source_card.get_loyalty_abilities()
    )
    _activate(game, player, source_card, loyalty_offset + index)


# ---------------------------------------------------------------------------
# advance_to_phase
# ---------------------------------------------------------------------------


def advance_to_phase(
    game: GameState,
    phase: Phase,
    step: Step | None = None,
) -> None:
    """Fast-forward the game state to the specified phase/step.

    Advances by calling :meth:`GameState.advance_phase` until the target
    phase (and optionally step) is reached.  Priority is not granted during
    fast-forwarding — this is a direct state manipulation for test setup.

    Parameters:
        game: The game state to advance.
        phase: The target phase.
        step: The target step (or ``None`` for main phases).

    Raises:
        TestSetupError: If the target phase/step is not found within
            a full turn cycle (prevents infinite loops).
    """
    target = (phase, step)

    # Validate that (phase, step) is a valid combination
    valid_targets = {(p, s) for p, s in _TURN_SEQUENCE}
    if target not in valid_targets:
        raise TestSetupError(
            f"Invalid phase/step combination: ({phase!r}, {step!r}). "
            f"Valid combinations: {sorted(valid_targets, key=lambda x: str(x))}"
        )

    # Already there?
    if (game.phase, game.step) == target:
        return

    # Advance up to a full turn's worth of steps to prevent infinite loops
    max_advances = len(_TURN_SEQUENCE) + 1
    for _ in range(max_advances):
        game.advance_phase()
        if (game.phase, game.step) == target:
            return

    raise TestSetupError(
        f"Could not reach phase/step ({phase!r}, {step!r}) within "
        f"a full turn cycle. Current: ({game.phase!r}, {game.step!r})"
    )


# ---------------------------------------------------------------------------
# declare_attackers
# ---------------------------------------------------------------------------


def declare_attackers(
    game: GameState,
    attacker_names: list[str],
) -> None:
    """Advance to combat and declare attackers by name.

    1. Advances to the Declare Attackers step if not already there.
    2. Finds creatures on the active player's battlefield matching the
       given names.
    3. Calls :func:`engine.combat.declare_attackers_step` with the
       attackers as an action-layer directive (no Player Query is
       raised — this is the imperative action channel).

    Parameters:
        game: The game state.
        attacker_names: Names of creatures to declare as attackers.

    Raises:
        TestSetupError: If any named creature is not found on the
            active player's battlefield, or if the creature cannot attack.
    """
    # Advance to declare attackers step
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_ATTACKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)

    active = game.active_player
    bf = game.get_battlefield(active)

    # Resolve attacker names to objects
    attackers: list[Any] = []
    bf_objects = bf.get_all()
    for name in attacker_names:
        found = None
        for obj in bf_objects:
            if getattr(obj, "name", None) == name and obj not in attackers:
                found = obj
                break
        if found is None:
            bf_names = [getattr(c, "name", repr(c)) for c in bf_objects]
            raise TestSetupError(
                f"Attacker {name!r} not found on active player's battlefield. "
                f"Battlefield contains: {bf_names}"
            )
        attackers.append(found)

    # Declaring attackers is an action-layer directive (not a query).
    game.combat_state.in_combat = True
    declare_attackers_step(game, attackers)


# ---------------------------------------------------------------------------
# declare_blockers
# ---------------------------------------------------------------------------


def declare_blockers(
    game: GameState,
    assignments: dict[str, list[str]],
) -> None:
    """Assign blockers by name mapping.

    Parameters:
        game: The game state.
        assignments: A mapping of ``{"attacker_name": ["blocker_name", ...]}``.
            Each attacker on the active player's battlefield is matched by
            name, and each blocker on the defending player's battlefield is
            matched by name.

    Raises:
        TestSetupError: If any named creature is not found.
    """
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_BLOCKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

    active = game.active_player
    defending = game.non_active_player

    active_bf = game.get_battlefield(active)
    defending_bf = game.get_battlefield(defending)

    active_objects = active_bf.get_all()
    defending_objects = defending_bf.get_all()

    # Build mapping of blocker_obj → attacker_obj
    block_map: dict[Any, Any] = {}

    for attacker_name, blocker_names in assignments.items():
        # Find attacker
        attacker = None
        for obj in active_objects:
            if getattr(obj, "name", None) == attacker_name:
                attacker = obj
                break
        if attacker is None:
            raise TestSetupError(
                f"Attacker {attacker_name!r} not found on active player's battlefield. "
                f"Available: {[getattr(c, 'name', repr(c)) for c in active_objects]}"
            )

        for blocker_name in blocker_names:
            blocker = None
            for obj in defending_objects:
                if getattr(obj, "name", None) == blocker_name and obj not in block_map:
                    blocker = obj
                    break
            if blocker is None:
                raise TestSetupError(
                    f"Blocker {blocker_name!r} not found on defending player's battlefield. "
                    f"Available: {[getattr(c, 'name', repr(c)) for c in defending_objects]}"
                )
            block_map[blocker] = attacker

    # Declaring blockers is an action-layer directive (not a query). When an
    # attacker is multi-blocked the engine raises a damage-order Player Query to
    # the attacker's controller — set a Baseline Intent on that player if so.
    declare_blockers_step(game, block_map)


def enter_permanent(game, player, card):
    """Set up a hand card, then enter through the canonical zone-transition pipeline."""
    from engine.zones import move_to_zone

    card.owner = player
    card.controller = player
    game.get_hand(player).add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
    return card


def advance_game_to_phase(game, phase, step=None):
    """Drive canonical phase transitions and their public boundary events.

    Consumes no script entries: the stack is resolved with every player
    passing before each transition.
    """
    for _ in range(len(_TURN_SEQUENCE) + 1):
        if (game.phase, game.step) == (phase, step):
            return
        # An abandoned resolution stops play where it is, as in any driver;
        # a later call resumes from there.
        if not _finish_forced(game) or not _enter_next_step(game):
            return
    raise TestSetupError("phase boundary was not reached")


def _enter_next_step(game: GameState, *, finish_cleanup_step: bool = True) -> bool:
    """Advance to the next step and perform its turn-based actions; a cleanup
    step is finished with every player passing unless ``finish_cleanup_step``
    is false, leaving its iterations to the caller. Returns ``False`` if
    finishing the cleanup stopped at an abandoned resolution."""
    from engine.combat import combat_damage_step, end_combat_step
    from engine.events import (
        BeginningOfCombatTriggeredEvent,
        BeginningOfUpkeepTriggeredEvent,
        EndOfTurnTriggeredEvent,
        EndStepTriggeredEvent,
    )
    from engine.game import draw_card
    from engine.turn import untap_step

    game.advance_phase()
    if game.step == Step.UNTAP:
        untap_step(game)
    elif game.step == Step.UPKEEP:
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    elif game.step == Step.DRAW:
        if game.get_library(game.active_player).get_all():
            draw_card(game, game.active_player)
    elif game.step == Step.BEGIN_COMBAT:
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
    elif game.step == Step.COMBAT_DAMAGE:
        combat_damage_step(game)
    elif game.step == Step.END_COMBAT:
        end_combat_step(game)
    elif game.step == Step.END:
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=game.active_player))
        game.trigger_manager.fire_event(game, EndOfTurnTriggeredEvent())
    elif game.step == Step.CLEANUP and finish_cleanup_step:
        return _finish_cleanup(game)
    return True


def behavioral_game():
    from engine.card import Creature

    game = create_game()
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
        for i in range(40):
            game.get_library(player).add(
                Creature(name=f"Library {i}", owner=player, base_power=2, base_toughness=2)
            )
    return game


def prefer(player, *decisions):
    player.set_baseline(Intent(pattern=GameRef(), preferences=tuple(decisions)))


def payment_preference(game, source):
    """Preferences that activate ``source``'s mana ability during payment,
    whether the engine asks for the permanent or for one of its abilities."""
    from engine.stack import object_current_zone

    zone = object_current_zone(game, source)
    if zone is None:
        raise TestSetupError("Mana source has not been placed in a zone")
    instance = game.refs.instance_id(source, zone)
    return (
        Decision.obj(instance=instance),
        Decision.ability(source=instance),
        Decision.ability(instance=instance),
    )


def object_preference(game, card):
    from engine.stack import object_current_zone

    zone = object_current_zone(game, card)
    if zone is None:
        raise TestSetupError("Choice object has not been placed in a zone")
    return Decision.obj(instance=game.refs.instance_id(card, zone))


def cast_vanilla_spell(game, seat, value=2):
    from engine.card import Instant
    from engine.types import ManaCost

    spell = Instant(
        name=f"Test spell {value}", owner=game.players[seat], mana_cost=ManaCost(generic=value)
    )
    game.get_hand(game.players[seat]).add(spell)
    game.players[seat].mana_pool.add(ManaType.COLORLESS, value)
    return _cast(game, game.players[seat], spell)


def ability_instance(game, player, source, index=0):
    """Prepare a reusable activation through the canonical public descriptor types."""
    from engine.abilities import ActivatedAbilityInstance
    from engine.card import ManaAbility

    descriptor = card_abilities(source)[index]
    is_mana = isinstance(descriptor, ManaAbility)
    return ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=descriptor.cost,
        effect=descriptor.mana_produced if is_mana else descriptor.effect,
        is_mana_ability=is_mana,
        description=descriptor.description,
        targeting=getattr(descriptor, "targeting", None),
        can_activate=getattr(descriptor, "can_activate", None),
    )


def cast_card(game, player, card, resolve=True):
    """Stage an unzoned card and cast it as a one-entry :func:`act` script; the
    test supplies mana and Intents. Returns what the engine's cast returned.

    Raises :class:`~engine.casting.CastingError` when the card is not offered
    at priority or the engine rejects the cast (rolled back).
    """
    from engine.casting import can_cast_at_instant_speed
    from engine.stack import object_current_zone

    if card.owner is None:
        card.owner = player
    card.controller = player
    zone = object_current_zone(game, card)
    if zone is None:
        game.get_hand(player).add(card)
    elif not game.get_hand(player).contains(card):
        raise TestSetupError("cast_card expects an unzoned card or one in the caster's hand")
    if not can_cast_at_instant_speed(card):
        game.active_player_index = game.players.index(player)
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    result = _cast(game, player, card)
    if resolve:
        resolve_stack(game)
    return result


def finish_cleanup(game):
    """Perform cleanup iterations until one grants no priority, resolving what
    each puts on the stack with every player passing; consumes no entries.
    Stops where a resolution is abandoned."""
    _finish_cleanup(game)


def _finish_cleanup(game: GameState) -> bool:
    from engine.turn import cleanup_iteration

    while cleanup_iteration(game):
        if not _drain_stack(game):
            return False
    return True


def scenario_game(*args, **kwargs):
    """Create an empty canonical game with deterministic first-offered defaults."""
    game = create_game(*args, **kwargs)
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    return game


def fund_mana_cost(player, cost):
    """Provide a specified cost's mana as test setup, without paying it."""
    for color, amount in cost.pips.items():
        player.mana_pool.add(color, amount)
    player.mana_pool.add(ManaType.COLORLESS, cost.generic)


def mana_ability_instance(game, player, source, index=0):
    from engine.abilities import ActivatedAbilityInstance

    descriptor = source.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=descriptor.cost,
        effect=descriptor.mana_produced,
        is_mana_ability=True,
        description=descriptor.description,
    )
