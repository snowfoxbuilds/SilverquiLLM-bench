"""Test utility helpers for the Test Oracle Workspace.

This module is the home of the **audited test API** defined in
docs/specs/AUDITED-TEST-API.md.  Audited tests may touch the engine *only*
through the allow-list below; everything is composed over canonical-public
engine entrypoints so the same API functions against the oracle engine and
against any candidate engine at evaluation time.

Allow-list (AUDITED-TEST-API.md):
    Setup:      create_game, set_board_state, set_player, PermanentSpec
    Advance:    priority_loop, advance_to_phase
    Players:    DeterministicPlayer, no_op, perform_action,
                perform_illegal_action, CastSpell, CastSpellFree,
                ActivateAbility, PlayLand
    Assertions: assert_in_zone, assert_zone_count, assert_zone_exact,
                assert_library_order, assert_tapped, assert_counters,
                assert_damage, assert_power_toughness, assert_stack,
                assert_on_stack, assert_stack_empty, assert_mana_pool,
                assert_colors_spent, assert_life_total
    Enums:      Phase, Step, Zone, ManaType, Color, CardType, Keyword

Legacy helpers (cast_spell, resolve_top, declare_attackers, declare_blockers,
set_mana_pool, set_hand, set_battlefield, set_library_top, set_graveyard,
assert_casting_error, card_colors) remain for the engine's own unit tests and
for pre-Phase-18 audited suites; they are *outside* the audited allow-list and
the API conformance test rejects their use in Phase-18 audited tests.
"""

from __future__ import annotations

import contextlib
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Generator

from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    LoyaltyAbilityInstance,
    activate_ability as _engine_activate_ability,
)
from engine.card import CardImpl
from engine.casting import CastingError, cast_spell as _engine_cast_spell
from engine.casting import cast_spell_free as _engine_cast_spell_free
from engine.casting import play_land as _engine_play_land
from engine.combat import (
    combat_damage_step as _combat_damage_step,
    declare_attackers_step as _declare_attackers_step,
    declare_blockers_step as _declare_blockers_step,
    end_combat_step as _end_combat_step,
)
from engine.game import create_game as _engine_create_game
from engine.game import discard as _engine_discard
from engine.game import draw_card as _engine_draw_card
from engine.game_state import GameState, _TURN_SEQUENCE
from engine.mana import ManaPool
from engine.player import DeterministicPlayer as _EngineDeterministicPlayer
from engine.player import ScriptExhaustedError
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Phase, Step, Zone


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
# DeterministicPlayer — two explicit channels
# ---------------------------------------------------------------------------
#
# Channel 1 (``script``)  — directive queue, polled by the host-side
#                           ``priority_loop`` each time the player holds
#                           priority.  Never seen by the engine.
# Channel 2 (``choices``) — choice script: the *canonical* answer deque the
#                           engine consumes via choose / choose_target /
#                           choose_yes_no / choose_card / assign_damage_order.
#
# The class subclasses the canonical engine ``DeterministicPlayer`` using only
# its canonical constructor signature, so it works against any candidate
# engine that implements the canonical public player API.


class DeterministicPlayer(_EngineDeterministicPlayer):
    """Scripted player with separate directive and choice channels.

    A dry queue on *either* channel fails the test (``ScriptExhaustedError``):
    the choice channel raises through the canonical ``_pop`` path; the
    directive channel raises in the host-side ``priority_loop`` poll.
    """

    def __init__(
        self,
        name: str,
        script: list[Any] | tuple[Any, ...] = (),
        choices: list[Any] | tuple[Any, ...] = (),
        life: int = 20,
    ) -> None:
        # The canonical answer deque (consumed by choose/choose_target/...)
        # IS the choice channel.
        super().__init__(name, list(choices), life)
        # Channel 1: host-side directive queue.
        self._directives: deque[Any] = deque(script)
        # Targets carried on the *current* directive, handed to the canonical
        # cast pipeline ahead of the choice script.
        self._pending_targets: deque[Any] = deque()

    def choose_target(self, options: Any, requirement: Any) -> Any:
        """Serve directive-carried targets first, then the choice script."""
        if self._pending_targets:
            return self._pending_targets.popleft()
        return super().choose_target(options, requirement)


# ---------------------------------------------------------------------------
# Directives & actions (Channel 1 vocabulary)
# ---------------------------------------------------------------------------


@dataclass
class _Directive:
    """One entry in a player's directive queue."""

    kind: str  # "no_op" | "perform" | "perform_illegal"
    action: Any = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"_Directive({self.kind}, {self.action!r})"


def no_op() -> _Directive:
    """Pass priority without acting."""
    return _Directive("no_op")


def perform_action(action: Any) -> _Directive:
    """Take an action the test asserts is legal.

    If the engine rejects the action (``CastingError`` / ``AbilityError``),
    the test fails.
    """
    return _Directive("perform", action)


def perform_illegal_action(action: Any) -> _Directive:
    """Take an action the test asserts is illegal.

    If the engine *accepts* the action, the test fails; an engine rejection
    (``CastingError`` / ``AbilityError``) is swallowed and the loop continues.
    """
    return _Directive("perform_illegal", action)


@dataclass
class CastSpell:
    """Cast a named spell.  ``from_zone != Zone.HAND`` routes through the
    test-layer alternate-zone cast helper (composition over the canonical
    cast path — never an engine change)."""

    name: str
    targets: list[Any] = field(default_factory=list)
    x: Any = None
    mode: Any = None
    mana: dict[ManaType, int] | None = None
    from_zone: Zone = Zone.HAND


@dataclass
class CastSpellFree:
    """Cast a named spell without paying its mana cost (canonical
    ``cast_spell_free``)."""

    name: str
    from_zone: Zone = Zone.HAND


@dataclass
class ActivateAbility:
    """Activate an ability of ``source``.

    ``ability`` is a printed-order index.  For planeswalkers it indexes
    ``get_loyalty_abilities()``; for other permanents it indexes the printed
    ability list — mana abilities (``get_mana_abilities()``) first, then
    ``get_activated_abilities()``.  Mana abilities resolve immediately into
    the pool; other abilities use the stack.
    """

    source: Any
    ability: int
    targets: list[Any] = field(default_factory=list)
    x: Any = None


@dataclass
class PlayLand:
    """Play a named land from hand (canonical ``play_land`` special action)."""

    name: str


# ---------------------------------------------------------------------------
# PermanentSpec — per-permanent setup state
# ---------------------------------------------------------------------------

_CANONICAL_COUNTER_KEYS = ("+1/+1", "-1/-1", "loyalty")


@dataclass
class PermanentSpec:
    """Per-permanent state for ``set_board_state``.

    ``name`` is a card object, or the name of a basic land
    (Plains/Island/Swamp/Mountain/Forest).  ``counters`` keys are limited to
    the canonical ``"+1/+1"``, ``"-1/-1"`` and ``"loyalty"``.
    """

    name: Any
    tapped: bool = False
    summoning_sick: bool = False
    counters: dict[str, int] = field(default_factory=dict)
    damage_marked: int = 0
    attachments: list[Any] = field(default_factory=list)
    controller: int | None = None


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
    seed: int | None = None,
) -> GameState:
    """Create a new two-player game from card lists.

    ``scripts`` (legacy) pre-loads the players' *choice* channel — the
    canonical answer deque.  Directive queues start empty; install them with
    ``set_player``.  ``seed`` seeds ``game.rng`` for deterministic
    coin-flips / random effects.
    """
    if deck1 is None:
        deck1 = []
    if deck2 is None:
        deck2 = []

    script1: list[Any] = []
    script2: list[Any] = []
    if scripts is not None:
        script1, script2 = scripts

    p1 = DeterministicPlayer(player1_name, script=[], choices=script1, life=player1_life)
    p2 = DeterministicPlayer(player2_name, script=[], choices=script2, life=player2_life)

    game = _engine_create_game(p1, p2, deck1, deck2)

    for player in game.players:
        if player.drawn_from_empty_library:
            player.drawn_from_empty_library = False

    if player1_life != 20:
        game.players[0].life = player1_life
    if player2_life != 20:
        game.players[1].life = player2_life

    if seed is not None:
        game.rng = random.Random(seed)

    return game


def set_player(game: GameState, player_index: int, player: DeterministicPlayer) -> None:
    """Install a scripted player at ``player_index``.

    The existing player object (already referenced as owner/controller by
    cards and trigger registrations) *adopts* the provided player's name,
    life, directive queue and choice script — object identity is preserved so
    prior ``set_board_state`` setup stays valid.  May be called again
    mid-test to load fresh scripts for a subsequent ``priority_loop``.
    """
    if not isinstance(player, DeterministicPlayer):
        raise TestSetupError(
            "set_player requires a test_utils.DeterministicPlayer instance"
        )
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players"
        )
    current = game.players[player_index]
    if not isinstance(current, DeterministicPlayer):
        raise TestSetupError(
            "set_player target is not a scripted player — use create_game()"
        )
    current.name = player.name
    current.life = player.life
    current._directives = player._directives
    current._script = player._script
    current._pending_targets.clear()


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
# set_board_state
# ---------------------------------------------------------------------------


def set_board_state(
    game: GameState,
    player_index: int,
    *,
    battlefield: list[Any] | None = None,
    hand: list[Any] | None = None,
    graveyard: list[Any] | None = None,
    library: list[Any] | None = None,
    exile: list[Any] | None = None,
    life: int | None = None,
    mana: dict[ManaType, int] | None = None,
) -> None:
    """Directly set zone contents and player state for test setup.

    ``library`` is ordered: index 0 is the *top* of the library.  Battlefield
    entries may be ``PermanentSpec`` to express per-permanent state (tapped,
    counters, marked damage, attachments, controller).  Entries in any zone
    may be card objects or basic-land names.
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
        set_mana_pool(game, player_index, mana)

    if battlefield is not None:
        _set_zone(game, player, Zone.BATTLEFIELD, battlefield)

    if hand is not None:
        _set_zone(game, player, Zone.HAND, hand)

    if graveyard is not None:
        _set_zone(game, player, Zone.GRAVEYARD, graveyard)

    if exile is not None:
        _set_zone(game, player, Zone.EXILE, exile)

    if library is not None:
        # Given top..bottom; the zone container stores bottom..top.
        _set_zone(game, player, Zone.LIBRARY, list(reversed(library)))


_BASIC_LAND_NAMES = ("Plains", "Island", "Swamp", "Mountain", "Forest")


def _materialize_card(entry: Any) -> Any:
    """Turn a setup entry into a card object.

    Strings are supported for basic lands only; anything else must be a card
    object the test constructed (or imported from ``card_impl``).
    """
    if isinstance(entry, str):
        if entry in _BASIC_LAND_NAMES:
            import engine.basic_lands as _basic_lands

            return getattr(_basic_lands, entry)(name=entry)
        raise TestSetupError(
            f"Cannot materialize card from name {entry!r} — only basic land "
            f"names are resolvable; pass a card object instead"
        )
    return entry


def _apply_permanent_spec(game: GameState, card: Any, spec: PermanentSpec) -> None:
    """Apply per-permanent state from a ``PermanentSpec`` to *card*."""
    if spec.tapped:
        if not hasattr(card, "is_tapped"):
            raise TestSetupError(f"{card!r} has no tapped state")
        card.is_tapped = True
    if hasattr(card, "summoning_sick"):
        card.summoning_sick = spec.summoning_sick
    if spec.damage_marked:
        if not hasattr(card, "damage_marked"):
            raise TestSetupError(f"{card!r} cannot have marked damage")
        card.damage_marked = spec.damage_marked
    for key, value in spec.counters.items():
        if key not in _CANONICAL_COUNTER_KEYS:
            raise TestSetupError(
                f"Counter type {key!r} is not canonical — only "
                f"{_CANONICAL_COUNTER_KEYS} are supported"
            )
        if key == "+1/+1":
            card.plus_one_counters = value
            card._base_plus_one_counters = value
        elif key == "-1/-1":
            card.minus_one_counters = value
            card._base_minus_one_counters = value
        else:  # loyalty
            if not hasattr(card, "loyalty"):
                raise TestSetupError(f"{card!r} has no loyalty")
            card.loyalty = value


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

    for entry in cards:
        spec: PermanentSpec | None = None
        if isinstance(entry, PermanentSpec):
            spec = entry
            card = _materialize_card(spec.name)
        else:
            card = _materialize_card(entry)

        controller = player
        if spec is not None and spec.controller is not None:
            controller = game.players[spec.controller]

        card.owner = player
        card.controller = controller

        if zone == Zone.BATTLEFIELD:
            destination = controller.zones[Zone.BATTLEFIELD]
        else:
            destination = zone_container
        destination.add(card)

        # When adding to the battlefield, register triggers and replacement
        # effects so that triggered abilities fire correctly during tests.
        # Also clear summoning sickness so creatures can attack immediately
        # (test setup assumption: cards are "already in play") unless the
        # PermanentSpec opts back in.
        if zone == Zone.BATTLEFIELD:
            if hasattr(card, "summoning_sick"):
                card.summoning_sick = False
            if hasattr(card, "register_triggers"):
                card.register_triggers(game)
            if hasattr(card, "register_replacement_effects"):
                card.register_replacement_effects(game)
            if spec is not None:
                _apply_permanent_spec(game, card, spec)
                for attachment in spec.attachments:
                    att = _materialize_card(attachment)
                    att.owner = player
                    att.controller = controller
                    att.attached_to = card
                    controller.zones[Zone.BATTLEFIELD].add(att)
                    if hasattr(att, "register_triggers"):
                        att.register_triggers(game)
                    if hasattr(att, "register_replacement_effects"):
                        att.register_replacement_effects(game)
        elif zone == Zone.EXILE:
            # Cards whose abilities function from exile (e.g. Paradigm
            # recurrence) need their triggers registered when placed there
            # directly by setup.
            if hasattr(card, "register_triggers"):
                card.register_triggers(game)


# ---------------------------------------------------------------------------
# Host-side driver internals
# ---------------------------------------------------------------------------

# Safety bound for driver loops; the pytest-timeout 30s backstop remains the
# last line of defense.
_MAX_DRIVER_ITERATIONS = 10_000


def _display_name(obj: Any) -> Any:
    source = getattr(obj, "source", None)
    if source is not None and getattr(source, "name", None) is not None:
        return source.name
    return getattr(obj, "name", repr(obj))


def _resolve_reference(game: GameState, ref: Any) -> Any:
    """Resolve a target/source reference to a game object.

    Non-string references pass through unchanged.  Strings are matched by
    name against (in order): both battlefields, the stack (returning the
    ``StackObject``), the players, then graveyards and exiles.
    """
    if not isinstance(ref, str):
        return ref
    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if getattr(obj, "name", None) == ref:
                return obj
    for stack_obj in game.stack.objects():
        if _display_name(stack_obj) == ref:
            return stack_obj
    for player in game.players:
        if player.name == ref:
            return player
    for zone in (Zone.GRAVEYARD, Zone.EXILE):
        for player in game.players:
            for obj in player.zones[zone].get_all():
                if getattr(obj, "name", None) == ref:
                    return obj
    raise TestSetupError(f"Could not resolve reference {ref!r} to a game object")


def _find_card_in_zone(player: Any, zone: Zone, name: str) -> Any:
    container = player.zones[zone]
    for obj in container.get_all():
        if getattr(obj, "name", None) == name:
            return obj
    names = [getattr(c, "name", repr(c)) for c in container.get_all()]
    zone_label = zone.name.lower()
    raise TestSetupError(
        f"Card {name!r} not found in player {player.name}'s {zone_label}. "
        f"{zone_label.capitalize()} contains: {names}"
    )


def _cast_spell_from_zone(game: GameState, player: Any, card: Any, from_zone: Zone) -> None:
    """Thin test-layer helper for alternate-zone casts (e.g. Prepared from
    exile).  Composes the canonical from-zone cast path; never an engine
    change."""
    _engine_cast_spell_free(game, player, card, from_zone)


def _cast_spell_with_payment(
    game: GameState,
    player: Any,
    card: Any,
    mana: dict[ManaType, int],
) -> None:
    """Run the canonical ``cast_spell`` pipeline with an explicit generic-mana
    split (the optional ``mana=`` directive disambiguator).

    The split is pre-validated against a scratch pool, then the player's
    ``pay`` is routed through the canonical ``pay(cost, choices=...)``
    parameter for the duration of the cast — composition over the canonical
    public payment API, never an engine change.
    """
    # Pre-validate the explicit split against a scratch copy of the pool.
    scratch = ManaPool()
    for mt in ManaType:
        amount = player.mana_pool.get(mt)
        if amount:
            scratch.add(mt, amount)
    from engine.casting import get_cost_reduction

    reduction = get_cost_reduction(game, card, player)
    cost = card.mana_cost
    if reduction > 0:
        cost = ManaCost(
            generic=max(0, cost.generic - reduction),
            pips=dict(cost.pips),
            x_count=cost.x_count,
            hybrid=list(cost.hybrid),
        )
    if not scratch.pay(cost, choices=dict(mana)):
        raise CastingError(
            f"Cannot cast {card.name!r} — explicit mana payment {mana!r} is "
            f"not a legal way to pay {cost!r}"
        )

    original_pay = player.mana_pool.pay

    def _pay_with_choices(pay_cost: ManaCost, choices: dict[ManaType, int] | None = None) -> bool:
        return original_pay(pay_cost, choices=dict(mana))

    player.mana_pool.pay = _pay_with_choices  # type: ignore[method-assign]
    try:
        _engine_cast_spell(game, player, card)
    finally:
        del player.mana_pool.pay


def _build_ability_instance(
    game: GameState, player: Any, action: ActivateAbility, source: Any
) -> Any:
    """Map a printed-order ability index to an engine ability instance."""
    if CardType.PLANESWALKER in getattr(source, "card_types", set()) and hasattr(
        source, "get_loyalty_abilities"
    ):
        abilities = source.get_loyalty_abilities()
        if not 0 <= action.ability < len(abilities):
            raise TestSetupError(
                f"{_display_name(source)!r} has {len(abilities)} loyalty "
                f"abilities; index {action.ability} is out of range"
            )
        ab = abilities[action.ability]
        return LoyaltyAbilityInstance(
            source=source,
            controller=player,
            loyalty_cost=ab.loyalty_cost,
            effect=ab.effect,
            description=ab.description,
        )

    mana_abilities = list(source.get_mana_abilities()) if hasattr(source, "get_mana_abilities") else []
    activated = list(source.get_activated_abilities()) if hasattr(source, "get_activated_abilities") else []
    combined = mana_abilities + activated
    if not 0 <= action.ability < len(combined):
        raise TestSetupError(
            f"{_display_name(source)!r} has {len(combined)} abilities; "
            f"index {action.ability} is out of range"
        )
    ab = combined[action.ability]
    if action.ability < len(mana_abilities):
        return ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=ab.cost,
            effect=ab.mana_produced,
            is_mana_ability=True,
            description=ab.description,
        )
    return ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=ab.cost,
        effect=ab.effect,
        is_mana_ability=False,
        description=ab.description,
    )


def _execute_action(game: GameState, player: Any, action: Any) -> None:
    """Execute one directive action through the canonical entrypoints.

    Raises ``CastingError`` / ``AbilityError`` when the engine rejects the
    action — the driver maps those onto perform_action /
    perform_illegal_action semantics.
    """
    if isinstance(action, CastSpell):
        if action.x is not None or action.mode is not None:
            raise TestSetupError(
                "CastSpell x=/mode= are not supported by the canonical cast "
                "path — no audited card requires them"
            )
        card = _find_card_in_zone(player, action.from_zone, action.name)
        targets = [_resolve_reference(game, t) for t in action.targets]
        player._pending_targets.extend(targets)
        try:
            if action.from_zone == Zone.HAND:
                if action.mana is not None:
                    _cast_spell_with_payment(game, player, card, action.mana)
                else:
                    _engine_cast_spell(game, player, card)
            else:
                _cast_spell_from_zone(game, player, card, action.from_zone)
        except Exception:
            player._pending_targets.clear()
            raise
        if player._pending_targets:
            leftover = list(player._pending_targets)
            player._pending_targets.clear()
            raise TestSetupError(
                f"CastSpell({action.name!r}) carried more targets than the "
                f"card requested; unconsumed: {leftover!r}"
            )
        return

    if isinstance(action, CastSpellFree):
        card = _find_card_in_zone(player, action.from_zone, action.name)
        _engine_cast_spell_free(game, player, card, action.from_zone)
        return

    if isinstance(action, PlayLand):
        card = _find_card_in_zone(player, Zone.HAND, action.name)
        _engine_play_land(game, player, card)
        return

    if isinstance(action, ActivateAbility):
        source = _resolve_reference(game, action.source)
        if action.x is not None:
            raise TestSetupError(
                "ActivateAbility x= is not supported by the canonical "
                "activation path — no audited card requires it"
            )
        instance = _build_ability_instance(game, player, action, source)
        if action.targets:
            # Canonical convention: targets chosen at activation live on the
            # source's ``chosen_targets`` (mirrors what _resolve_spell does
            # for spells).
            source.chosen_targets = [_resolve_reference(game, t) for t in action.targets]
        _engine_activate_ability(game, player, instance)
        return

    raise TestSetupError(f"Unknown directive action: {action!r}")


def _resolve_one_stack_object(game: GameState) -> None:
    """Resolve exactly one stack object, then re-check state-based actions."""
    obj = game.stack.pop()
    obj.on_resolve(game)
    resolve_state_based_actions(game)


def _drain_stack(game: GameState) -> None:
    """Resolve the stack one object at a time (used by ``advance_to_phase``,
    which opens no priority windows)."""
    iterations = 0
    while not game.stack.is_empty():
        iterations += 1
        if iterations > _MAX_DRIVER_ITERATIONS:
            raise TestSetupError("advance_to_phase: stack failed to drain")
        _resolve_one_stack_object(game)


# ---------------------------------------------------------------------------
# priority_loop — the host-side driver
# ---------------------------------------------------------------------------


def priority_loop(game: GameState) -> None:
    """Advance the game by polling player directive queues (APNAP).

    Per iteration: resolve state-based actions, poll each player in APNAP
    order for one directive, execute actions host-side through the canonical
    entrypoints (retain-on-action: an acting player causes a re-poll from the
    active player), and — when nobody acts and the stack is non-empty —
    resolve exactly one stack object.  Terminates when the stack is empty and
    every directive queue is exhausted.  A directive poll against a dry queue
    while the stack is non-empty raises ``ScriptExhaustedError``.
    """
    iterations = 0
    while True:
        iterations += 1
        if iterations > _MAX_DRIVER_ITERATIONS:
            raise TestSetupError("priority_loop failed to converge")

        resolve_state_based_actions(game)

        players = [game.active_player, game.non_active_player]
        for player in players:
            if not isinstance(player, DeterministicPlayer):
                raise TestSetupError(
                    "priority_loop requires scripted players — use "
                    "create_game() / set_player()"
                )

        if game.stack.is_empty() and all(not p._directives for p in players):
            return

        acted = False
        for player in players:
            queue = player._directives
            if not queue:
                if game.stack.is_empty():
                    continue  # nothing left to say; remaining players may act
                raise ScriptExhaustedError(
                    f"Player {player.name!r} was polled for a directive with "
                    f"the stack non-empty but the directive queue is dry"
                )
            directive = queue.popleft()
            if directive.kind == "no_op":
                continue  # pass priority
            try:
                _execute_action(game, player, directive.action)
            except (CastingError, AbilityError) as exc:
                player._pending_targets.clear()
                if directive.kind == "perform":
                    raise AssertionError(
                        f"perform_action: the engine rejected "
                        f"{directive.action!r} as illegal: {exc}"
                    ) from exc
                # perform_illegal: the rejection is the expected outcome.
            else:
                if directive.kind == "perform_illegal":
                    raise AssertionError(
                        f"perform_illegal_action: the engine ACCEPTED "
                        f"{directive.action!r} — expected it to be illegal"
                    )
            acted = True
            break  # retain-on-action: re-poll from the active player

        if not acted and not game.stack.is_empty():
            _resolve_one_stack_object(game)


# ---------------------------------------------------------------------------
# advance_to_phase — sanctioned fast-forward
# ---------------------------------------------------------------------------


def _process_turn_based_actions(game: GameState) -> None:
    """Run the turn-based actions for the step the game just entered.

    Mirrors the canonical turn loop's per-step actions without opening any
    priority window.  Combat declarations are answered from the players'
    choice scripts via the canonical combat steps.
    """
    current = (game.phase, game.step)

    if current == (Phase.BEGINNING, Step.UNTAP):
        active = game.active_player
        for obj in active.zones[Zone.BATTLEFIELD].get_all():
            if hasattr(obj, "is_tapped"):
                obj.is_tapped = False
            if hasattr(obj, "summoning_sick"):
                obj.summoning_sick = False
        active.land_plays_remaining = 1
    elif current == (Phase.BEGINNING, Step.UPKEEP):
        from engine.events import BeginningOfUpkeepTriggeredEvent

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    elif current == (Phase.BEGINNING, Step.DRAW):
        # The starting player skips their draw on turn 1 (rule 103.7a).
        if not (game.turn_number == 1 and game.active_player_index == 0):
            _engine_draw_card(game, game.active_player)
    elif game.phase == Phase.COMBAT and game.step is not None:
        if game.step == Step.DECLARE_ATTACKERS:
            _declare_attackers_step(game)
        elif game.step == Step.DECLARE_BLOCKERS:
            _declare_blockers_step(game)
        elif game.step == Step.COMBAT_DAMAGE:
            _combat_damage_step(game)
        elif game.step == Step.END_COMBAT:
            _end_combat_step(game)
    elif current == (Phase.ENDING, Step.CLEANUP):
        _cleanup_step(game)


def _cleanup_step(game: GameState, _depth: int = 0) -> None:
    """Host-side duplicate of the canonical cleanup step (rule 514).

    Forced choices (discard to hand size) are answered from the choice
    script; no priority window is opened.
    """
    if _depth > 16:
        raise TestSetupError("cleanup step failed to stabilise")

    active = game.active_player
    hand = active.zones[Zone.HAND]
    while len(hand) > 7:
        cards_in_hand = hand.get_all()
        chosen = active.choose_card(cards_in_hand, "discard to hand size")
        if chosen is None or not hand.contains(chosen):
            chosen = cards_in_hand[-1]
        _engine_discard(game, active, chosen)

    if hasattr(game, "effect_manager"):
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if hasattr(obj, "end_of_turn_cleanup"):
                obj.end_of_turn_cleanup()

    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if hasattr(obj, "damage_marked"):
                obj.damage_marked = 0
            if hasattr(obj, "dealt_deathtouch_damage"):
                obj.dealt_deathtouch_damage = False
            if hasattr(obj, "is_attacking"):
                obj.is_attacking = False
            if hasattr(obj, "is_blocking"):
                obj.is_blocking = False
    if hasattr(game, "combat_state"):
        game.combat_state.clear()

    game.empty_mana_pools()

    sba_happened = resolve_state_based_actions(game)
    if sba_happened or not game.stack.is_empty():
        _drain_stack(game)
        _cleanup_step(game, _depth + 1)


def advance_to_phase(
    game: GameState,
    phase: Phase,
    step: Step | None = None,
) -> None:
    """Fast-forward turn structure to the given phase/step.

    Processes the engine's turn-based actions, triggered abilities (resolved
    one at a time) and end-of-turn cleanup for every step *entered* — state is
    correct on arrival — but opens **no** priority windows.  A triggered
    ability that forces a choice is answered FIFO from the player's choice
    script (dry → ``ScriptExhaustedError``).  Crossing a turn boundary is out
    of scope (multi-player turn control is deferred).
    """
    target = (phase, step)
    if target not in _TURN_SEQUENCE:
        raise TestSetupError(
            f"Invalid phase/step combination: ({phase!r}, {step!r})."
        )
    current = (game.phase, game.step)
    if current == target:
        return
    current_idx = _TURN_SEQUENCE.index(current)
    target_idx = _TURN_SEQUENCE.index(target)
    if target_idx < current_idx:
        raise TestSetupError(
            f"advance_to_phase cannot cross a turn boundary: current "
            f"{current!r} is after target {target!r} in the turn sequence"
        )

    while (game.phase, game.step) != target:
        game.advance_phase()
        _process_turn_based_actions(game)
        _drain_stack(game)
        resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# Assertion helpers — observable state only
# ---------------------------------------------------------------------------


def _zone_display_names(game: GameState, player_index: int, zone: Zone) -> list[Any]:
    player = game.players[player_index]
    return [getattr(c, "name", repr(c)) for c in player.zones[zone].get_all()]


def _name_of(card: Any) -> str:
    if isinstance(card, str):
        return card
    return getattr(card, "name", repr(card))


def _find_permanent(game: GameState, perm: Any) -> Any:
    """Resolve a permanent reference (object or name) for assertions."""
    if not isinstance(perm, str):
        return perm
    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if getattr(obj, "name", None) == perm:
                return obj
    raise AssertionError(
        f"No permanent named {perm!r} found on either battlefield"
    )


def assert_in_zone(
    game: GameState,
    player_index: int,
    zone: Zone,
    card: Any,
    count: int = 1,
) -> None:
    """Assert that exactly ``count`` cards with the given name are in *zone*."""
    name = _name_of(card)
    names = _zone_display_names(game, player_index, zone)
    actual = sum(1 for n in names if n == name)
    if actual != count:
        raise AssertionError(
            f"Expected {count} × {name!r} in {zone.name} for player "
            f"{player_index}, found {actual}. Zone contains: {names}"
        )


def assert_zone_count(game: GameState, player_index: int, zone: Zone, n: int) -> None:
    """Assert the total number of objects in a zone."""
    names = _zone_display_names(game, player_index, zone)
    if len(names) != n:
        raise AssertionError(
            f"Expected {n} objects in {zone.name} for player {player_index}, "
            f"found {len(names)}: {names}"
        )


def assert_zone_exact(
    game: GameState, player_index: int, zone: Zone, cards: list[Any]
) -> None:
    """Assert zone contents match exactly (order-insensitive, by name)."""
    expected = sorted(_name_of(c) for c in cards)
    actual = sorted(_zone_display_names(game, player_index, zone))
    if expected != actual:
        raise AssertionError(
            f"{zone.name} for player {player_index} expected {expected}, "
            f"got {actual}"
        )


def assert_library_order(
    game: GameState, player_index: int, cards: list[Any]
) -> None:
    """Assert ordered library contents (index 0 = top of library)."""
    expected = [_name_of(c) for c in cards]
    player = game.players[player_index]
    # Zone container stores bottom..top; present top..bottom.
    actual = [
        getattr(c, "name", repr(c))
        for c in reversed(player.zones[Zone.LIBRARY].get_all())
    ]
    if expected != actual:
        raise AssertionError(
            f"Library (top..bottom) for player {player_index} expected "
            f"{expected}, got {actual}"
        )


def assert_tapped(game: GameState, perm: Any, tapped: bool = True) -> None:
    """Assert a permanent's tapped state."""
    obj = _find_permanent(game, perm)
    actual = getattr(obj, "is_tapped", None)
    if actual is None:
        raise AssertionError(f"{_name_of(perm)!r} has no tapped state")
    if actual != tapped:
        raise AssertionError(
            f"Expected {_name_of(perm)!r} tapped={tapped}, got {actual}"
        )


def assert_counters(game: GameState, perm: Any, counters: dict[str, int]) -> None:
    """Assert canonical counter amounts (``+1/+1``, ``-1/-1``, ``loyalty``)."""
    obj = _find_permanent(game, perm)
    for key, expected in counters.items():
        if key not in _CANONICAL_COUNTER_KEYS:
            raise AssertionError(
                f"Counter type {key!r} is not canonical — only "
                f"{_CANONICAL_COUNTER_KEYS} can be asserted"
            )
        if key == "+1/+1":
            actual = getattr(obj, "plus_one_counters", 0)
        elif key == "-1/-1":
            actual = getattr(obj, "minus_one_counters", 0)
        else:
            actual = getattr(obj, "loyalty", None)
        if actual != expected:
            raise AssertionError(
                f"Expected {_name_of(perm)!r} to have {expected} {key!r} "
                f"counters, got {actual}"
            )


def assert_damage(game: GameState, perm: Any, n: int) -> None:
    """Assert marked damage on a permanent."""
    obj = _find_permanent(game, perm)
    actual = getattr(obj, "damage_marked", 0)
    if actual != n:
        raise AssertionError(
            f"Expected {_name_of(perm)!r} to have {n} damage marked, got {actual}"
        )


def assert_power_toughness(
    game: GameState, perm: Any, power: int, toughness: int
) -> None:
    """Assert current power/toughness (after all effects)."""
    obj = _find_permanent(game, perm)
    actual_p = getattr(obj, "power", None)
    actual_t = getattr(obj, "toughness", None)
    if (actual_p, actual_t) != (power, toughness):
        raise AssertionError(
            f"Expected {_name_of(perm)!r} to be {power}/{toughness}, "
            f"got {actual_p}/{actual_t}"
        )


def assert_stack(game: GameState, names: list[Any]) -> None:
    """Assert ordered stack contents (index 0 = top of stack).

    Note: ``priority_loop`` only terminates with a fully drained stack and
    ``advance_to_phase`` drains as it goes, so after a sanctioned advancer
    this is in practice an ordered-emptiness assertion — mid-stack states
    are not observable under the audited driver.
    """
    expected = [_name_of(n) for n in names]
    actual = [_display_name(obj) for obj in game.stack.objects()]
    if expected != actual:
        raise AssertionError(
            f"Expected stack (top..bottom) {expected}, got {actual}"
        )


def assert_on_stack(game: GameState, card_name: str, count: int | None = None) -> None:
    """Assert that a card/spell with the given name is on the stack.

    With ``count``, assert exactly that many copies (``count=0`` asserts
    absence).  Note: the sanctioned advancers always drain the stack, so
    after them only absence/zero-count assertions carry signal; doubled
    resolutions (casualty) are asserted via the doubled observable result.
    """
    stack_names = [_display_name(obj) for obj in game.stack.objects()]
    actual = sum(1 for n in stack_names if n == card_name)
    if count is None:
        if actual == 0:
            raise AssertionError(
                f"Expected {card_name!r} on the stack, but stack contains: "
                f"{stack_names}"
            )
    elif actual != count:
        raise AssertionError(
            f"Expected {count} × {card_name!r} on the stack, found {actual}. "
            f"Stack contains: {stack_names}"
        )


def assert_stack_empty(game: GameState) -> None:
    """Assert the stack is empty."""
    if not game.stack.is_empty():
        stack_names = [_display_name(obj) for obj in game.stack.objects()]
        raise AssertionError(f"Expected empty stack, but it contains: {stack_names}")


def assert_mana_pool(
    game: GameState, player_index: int, mana: dict[ManaType, int]
) -> None:
    """Assert the full contents of a player's mana pool.

    Mana types not present in *mana* are asserted to be 0.  This is also the
    basis for the mana-spent pool-delta pattern.
    """
    pool = game.players[player_index].mana_pool
    actual = {mt: pool.get(mt) for mt in ManaType if pool.get(mt)}
    expected = {mt: amount for mt, amount in mana.items() if amount}
    if actual != expected:
        raise AssertionError(
            f"Expected player {player_index} mana pool {expected!r}, "
            f"got {actual!r}"
        )


def assert_colors_spent(
    game: GameState, colors: list[Color], player_index: int = 0
) -> None:
    """Assert the colors of the player's last mana payment."""
    pool = game.players[player_index].mana_pool
    actual = set(pool.last_payment_colors)
    expected = set(colors)
    if actual != expected:
        raise AssertionError(
            f"Expected colors spent {sorted(c.value for c in expected)}, "
            f"got {sorted(c.value for c in actual)}"
        )


def assert_life_total(game: GameState, player_index: int, n: int) -> None:
    """Assert a player's life total."""
    actual = game.players[player_index].life
    if actual != n:
        raise AssertionError(
            f"Expected player {player_index} life total {n}, got {actual}"
        )


def assert_casting_error() -> Any:
    """Context manager that asserts a CastingError is raised.

    Legacy helper — outside the audited allow-list (audited tests assert
    illegality via ``perform_illegal_action`` instead).
    """
    return _assert_casting_error()


@contextlib.contextmanager
def _assert_casting_error() -> Generator[None, None, None]:
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
# Legacy step helpers (engine unit tests / pre-Phase-18 suites only — outside
# the audited allow-list)
# ---------------------------------------------------------------------------


def resolve_top(game: GameState) -> None:
    """Resolve only the top spell/ability on the stack (one object)."""
    if game.stack.is_empty():
        return
    _resolve_one_stack_object(game)


def _resolve_top_of_stack(game: GameState) -> None:
    """Resolve the entire stack by repeatedly resolving the top object."""
    while not game.stack.is_empty():
        _resolve_one_stack_object(game)


def cast_spell(
    game: GameState,
    player_index: int,
    card_name: str,
    targets: list[Any] | None = None,
    *,
    zone: Zone = Zone.HAND,
) -> None:
    """Find a card by name, cast it, and pass priority until resolved.

    Legacy auto-draining helper — outside the audited allow-list.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players"
        )

    player = game.players[player_index]
    card = _find_card_in_zone(player, zone, card_name)

    # Feed targets to the canonical pipeline ahead of the choice script.
    if targets:
        if isinstance(player, DeterministicPlayer):
            player._pending_targets.extend(targets)
        elif isinstance(player, _EngineDeterministicPlayer):
            for target in reversed(targets):
                player._script.appendleft(target)

    if zone == Zone.HAND:
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
            if isinstance(player, DeterministicPlayer):
                player._pending_targets.clear()
            raise TestSetupError(
                f"Failed to cast {card_name!r}: {exc}"
            ) from exc
    else:
        try:
            _engine_cast_spell_free(game, player, card, zone)
        except Exception as exc:
            if isinstance(player, DeterministicPlayer):
                player._pending_targets.clear()
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
    """Cast a spell from exile (legacy wrapper around cast_spell with zone=Zone.EXILE)."""
    cast_spell(game, player_index, card_name, targets, zone=Zone.EXILE)


def _jump_to_phase(game: GameState, phase: Phase, step: Step | None = None) -> None:
    """Raw phase jump for the legacy step helpers: advances the turn marker
    without processing turn-based actions or opening choice prompts (the
    pre-Phase-18 ``advance_to_phase`` behaviour)."""
    target = (phase, step)
    if target not in _TURN_SEQUENCE:
        raise TestSetupError(
            f"Invalid phase/step combination: ({phase!r}, {step!r})."
        )
    if (game.phase, game.step) == target:
        return
    for _ in range(len(_TURN_SEQUENCE) + 1):
        game.advance_phase()
        if (game.phase, game.step) == target:
            return
    raise TestSetupError(
        f"Could not reach phase/step ({phase!r}, {step!r}) within a full turn cycle."
    )


def declare_attackers(
    game: GameState,
    attacker_names: list[str],
) -> None:
    """Advance to combat and declare attackers by name (legacy helper)."""
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_ATTACKERS):
        _jump_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)

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

    if isinstance(active, _EngineDeterministicPlayer):
        active._script.appendleft(attackers)
    else:
        raise TestSetupError(
            "declare_attackers requires active player to be a DeterministicPlayer"
        )
    game.combat_state.in_combat = True
    _declare_attackers_step(game)


def declare_blockers(
    game: GameState,
    assignments: dict[str, list[str]],
) -> None:
    """Assign blockers by name mapping (legacy helper)."""
    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_BLOCKERS):
        _jump_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

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

    if isinstance(defending, _EngineDeterministicPlayer):
        defending._script.appendleft(block_map)
    else:
        raise TestSetupError(
            "declare_blockers requires defending player to be a DeterministicPlayer"
        )
    _declare_blockers_step(game)
