"""Test utility helpers for the Test Oracle Workspace.

Extends the canonical workspace test_utils with additional helpers needed
by oracle implementations and rewritten audited tests.

Helpers:
    set_mana_pool — directly set a player's mana pool.
    set_hand — set the contents of a player's hand zone.
    set_battlefield — set the contents of a player's battlefield zone.
    set_library_top — set cards on top of a player's library.
    set_graveyard — set the contents of a player's graveyard zone.
    assert_on_ assert a card/spell is on the stack.stack 
    assert_in_zone — assert a card is in a specified zone.
    assert_casting_error — context manager asserting CastingError is raised.
    resolve_top — resolve the top spell/ability on the stack.
    cast_spell_from_exile — cast a spell from exile (free-cast).
"""

from __future__ import annotations

import contextlib
from typing import Any, Generator

from engine.card import CardImpl, Creature
from engine.casting import CastingError, cast_spell as _engine_cast_spell
from engine.casting import cast_spell_free as _engine_cast_spell_free
from engine.combat import (
    CombatState,
    declare_attackers_step,
    declare_blockers_step,
)
from engine.game import create_game as _engine_create_game
from engine.game_state import GameState, _TURN_SEQUENCE
from engine.mana import ManaPool
from engine.player import DeterministicPlayer
from engine.stack import priority_loop
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaType, Phase, Step, Zone


class TestSetupError(Exception):
    """Raised when a test utility function encounters an invalid setup."""


def card_colors(card: Any) -> set[str]:
    """Return a card's colors as single-letter strings, derived from its mana cost."""
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
    scripts: tuple[list[Any], list[Any]] | None = None,
) -> GameState:
    """Create a new two-player game from card lists."""
    if deck1 is None:
        deck1 = []
    if deck2 is None:
        deck2 = []

    script1: list[Any] = []
    script2: list[Any] = []
    if scripts is not None:
        script1, script2 = scripts

    p1 = DeterministicPlayer(player1_name, script=script1, life=player1_life)
    p2 = DeterministicPlayer(player2_name, script=script2, life=player2_life)

    game = _engine_create_game(p1, p2, deck1, deck2)

    for player in game.players:
        if player.drawn_from_empty_library:
            player.drawn_from_empty_library = False

    if player1_life != 20:
        game.players[0].life = player1_life
    if player2_life != 20:
        game.players[1].life = player2_life

    return game


# ---------------------------------------------------------------------------
# Zone manipulation helpers
# ---------------------------------------------------------------------------


def set_mana_pool(
    game: GameState,
    player_index: int,
    mana: dict[ManaType, int],
) -> None:
    """Directly set a player's mana pool, replacing existing mana."""
    player = game.players[player_index]
    player.mana_pool.empty()
    for mana_type, amount in mana.items():
        player.mana_pool.add(mana_type, amount)


def set_hand(
    game: GameState,
    player_index: int,
    cards: list[Any],
) -> None:
    """Set the contents of a player's hand zone."""
    player = game.players[player_index]
    _set_zone(game, player, Zone.HAND, cards)


def set_battlefield(
    game: GameState,
    player_index: int,
    cards: list[Any],
) -> None:
    """Set the contents of a player's battlefield zone."""
    player = game.players[player_index]
    _set_zone(game, player, Zone.BATTLEFIELD, cards)


def set_library_top(
    game: GameState,
    player_index: int,
    cards: list[Any],
) -> None:
    """Set cards on top of a player's library.

    The first card in *cards* will be the topmost card.
    Existing library contents below the new cards are preserved.
    """
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    # Insert cards at the top (in reverse order so first in list ends on top)
    for card in reversed(cards):
        card.owner = player
        card.controller = player
        library.add(card, position="top")


def set_graveyard(
    game: GameState,
    player_index: int,
    cards: list[Any],
) -> None:
    """Set the contents of a player's graveyard zone."""
    player = game.players[player_index]
    _set_zone(game, player, Zone.GRAVEYARD, cards)


# ---------------------------------------------------------------------------
# set_board_state (canonical compatibility)
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
    """Directly set zone contents and player state for test setup."""
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players (indices 0–{len(game.players) - 1})"
        )

    player = game.players[player_index]

    if life is not None:
        player.life = life

    if mana is not None:
        set_mana_pool(game, player_index, mana)

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
    """Replace a zone's contents with *cards*, assigning ownership."""
    zone_container = player.zones[zone]
    for obj in zone_container.get_all():
        zone_container.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        zone_container.add(card)
        # When adding to the battlefield, register triggers and replacement
        # effects so that triggered abilities fire correctly during tests.
        # Also clear summoning sickness so creatures can attack immediately
        # (test setup assumption: cards are "already in play").
        if zone == Zone.BATTLEFIELD:
            if hasattr(card, "summoning_sick"):
                card.summoning_sick = False
            if hasattr(card, "register_triggers"):
                card.register_triggers(game)
            if hasattr(card, "register_replacement_effects"):
                card.register_replacement_effects(game)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_on_stack(game: GameState, card_name: str) -> None:
    """Assert that a card/spell with the given name is on the stack.

    Raises AssertionError if not found.
    """
    for obj in game.stack.objects():
        source = getattr(obj, "source", None)
        if source is not None and getattr(source, "name", None) == card_name:
            return
        if getattr(obj, "name", None) == card_name:
            return
    stack_names = []
    for obj in game.stack.objects():
        source = getattr(obj, "source", None)
        if source:
            stack_names.append(getattr(source, "name", repr(obj)))
        else:
            stack_names.append(getattr(obj, "name", repr(obj)))
    raise AssertionError(
        f"Expected {card_name!r} on the stack, but stack contains: {stack_names}"
    )


def assert_in_zone(
    game: GameState,
    player_index: int,
    zone: Zone,
    card_name: str,
) -> None:
    """Assert that a card with the given name is in the specified zone.

    Raises AssertionError if not found.
    """
    player = game.players[player_index]
    zone_container = player.zones[zone]
    for obj in zone_container.get_all():
        if getattr(obj, "name", None) == card_name:
            return
    zone_names = [getattr(c, "name", repr(c)) for c in zone_container.get_all()]
    raise AssertionError(
        f"Expected {card_name!r} in {zone.name} for player {player_index}, "
        f"but zone contains: {zone_names}"
    )


@contextlib.contextmanager
def assert_casting_error() -> Generator[None, None, None]:
    """Context manager that asserts a CastingError is raised."""
    try:
        yield
    except CastingError:
        return
    except TestSetupError as exc:
        # Only accept if the original cause was actually a CastingError
        if isinstance(exc.__cause__, CastingError):
            return
        raise AssertionError(
            f"Expected CastingError but got TestSetupError caused by "
            f"{type(exc.__cause__).__name__}: {exc}"
        ) from exc
    else:
        raise AssertionError("Expected CastingError but no exception was raised")


# ---------------------------------------------------------------------------
# resolve_top
# ---------------------------------------------------------------------------


def resolve_top(game: GameState) -> None:
    """Resolve only the top spell/ability on the stack (one object).

    Both players pass priority so the top of the stack resolves.
    Unlike _resolve_top_of_stack(), this does NOT drain the entire stack —
    it resolves exactly one object and returns.
    """
    if game.stack.is_empty():
        return
    obj = game.stack.pop()
    obj.on_resolve(game)
    resolve_state_based_actions(game)


def _resolve_top_of_stack(game: GameState) -> None:
    """Resolve the entire stack by repeatedly resolving the top object.

    Both players pass priority so the top of the stack resolves.
    Repeats until the stack is empty (drains follow-up triggers).
    """
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# cast_spell  (canonical — from hand)
# ---------------------------------------------------------------------------


def cast_spell(
    game: GameState,
    player_index: int,
    card_name: str,
    targets: list[Any] | None = None,
    *,
    zone: Zone = Zone.HAND,
) -> None:
    """Find a card by name, cast it, and pass priority until resolved.

    Supports casting from hand (default) or from exile via ``zone=Zone.EXILE``.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players"
        )

    player = game.players[player_index]

    if zone == Zone.HAND:
        hand = game.get_hand(player)
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
    else:
        # Cast from a non-hand zone (e.g. exile)
        zone_container = player.zones[zone]
        card = None
        for obj in zone_container.get_all():
            if getattr(obj, "name", None) == card_name:
                card = obj
                break
        if card is None:
            zone_names = [getattr(c, "name", repr(c)) for c in zone_container.get_all()]
            raise TestSetupError(
                f"Card {card_name!r} not found in player {player_index}'s {zone.name}. "
                f"Zone contains: {zone_names}"
            )

    # Script targets
    if targets and isinstance(player, DeterministicPlayer):
        for target in reversed(targets):
            player._script.appendleft(target)

    if zone == Zone.HAND:
        # Normal cast from hand
        from engine.types import CardType, Keyword

        is_instant = CardType.INSTANT in getattr(card, "card_types", set())
        has_flash = Keyword.FLASH in getattr(card, "keywords", Keyword(0))

        if not is_instant and not has_flash:
            game.active_player_index = player_index
            game.priority_player_index = player_index
            if game.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
                game.phase = Phase.PRECOMBAT_MAIN
                game.step = None

        if not game.stack.is_empty():
            raise TestSetupError(
                f"Cannot cast {card_name!r} — stack is not empty"
            )

        try:
            _engine_cast_spell(game, player, card)
        except Exception as exc:
            raise TestSetupError(
                f"Failed to cast {card_name!r}: {exc}"
            ) from exc
    else:
        # Free-cast from non-hand zone
        try:
            _engine_cast_spell_free(game, player, card, zone)
        except Exception as exc:
            raise TestSetupError(
                f"Failed to cast {card_name!r} from {zone.name}: {exc}"
            ) from exc

    _resolve_top_of_stack(game)


def cast_spell_from_exile(
    game: GameState,
    player_index: int,
    card_name: str,
    targets: list[Any] | None = None,
) -> None:
    """Cast a spell from exile (convenience wrapper around cast_spell with zone=Zone.EXILE)."""
    cast_spell(game, player_index, card_name, targets, zone=Zone.EXILE)


# ---------------------------------------------------------------------------
# advance_to_phase
# ---------------------------------------------------------------------------


def advance_to_phase(
    game: GameState,
    phase: Phase,
    step: Step | None = None,
) -> None:
    """Fast-forward the game state to the specified phase/step."""
    target = (phase, step)
    valid_targets = {(p, s) for p, s in _TURN_SEQUENCE}
    if target not in valid_targets:
        raise TestSetupError(
            f"Invalid phase/step combination: ({phase!r}, {step!r})."
        )
    if (game.phase, game.step) == target:
        return
    max_advances = len(_TURN_SEQUENCE) + 1
    for _ in range(max_advances):
        game.advance_phase()
        if (game.phase, game.step) == target:
            return
    raise TestSetupError(
        f"Could not reach phase/step ({phase!r}, {step!r}) within a full turn cycle."
    )


# ---------------------------------------------------------------------------
# declare_attackers / declare_blockers
# ---------------------------------------------------------------------------


def declare_attackers(
    game: GameState,
    attacker_names: list[str],
) -> None:
    """Advance to combat and declare attackers by name."""
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_ATTACKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)

    active = game.active_player
    bf = game.get_battlefield(active)
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

    if isinstance(active, DeterministicPlayer):
        active._script.appendleft(attackers)
    else:
        raise TestSetupError(
            "declare_attackers requires active player to be a DeterministicPlayer"
        )
    game.combat_state.in_combat = True
    declare_attackers_step(game)


def declare_blockers(
    game: GameState,
    assignments: dict[str, list[str]],
) -> None:
    """Assign blockers by name mapping."""
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_BLOCKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

    active = game.active_player
    defending = game.non_active_player
    active_bf = game.get_battlefield(active)
    defending_bf = game.get_battlefield(defending)
    active_objects = active_bf.get_all()
    defending_objects = defending_bf.get_all()

    block_map: dict[Any, Any] = {}
    for attacker_name, blocker_names in assignments.items():
        attacker = None
        for obj in active_objects:
            if getattr(obj, "name", None) == attacker_name:
                attacker = obj
                break
        if attacker is None:
            raise TestSetupError(
                f"Attacker {attacker_name!r} not found on active player's battlefield."
            )
        for blocker_name in blocker_names:
            blocker = None
            for obj in defending_objects:
                if getattr(obj, "name", None) == blocker_name and obj not in block_map:
                    blocker = obj
                    break
            if blocker is None:
                raise TestSetupError(
                    f"Blocker {blocker_name!r} not found on defending player's battlefield."
                )
            block_map[blocker] = attacker

    if isinstance(defending, DeterministicPlayer):
        defending._script.appendleft(block_map)
    else:
        raise TestSetupError(
            "declare_blockers requires defending player to be a DeterministicPlayer"
        )
    declare_blockers_step(game)
