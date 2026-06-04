"""API conformance meta-test: only the audited test API may touch the engine.

Statically scans every Phase-18 audited test file (``tests/audited/**/sos_*/
tests.py`` in the oracle workspace, plus the canonical copies of the same
collector directories under ``benchmarks/sos/data/tests/audited``) and fails
if any file reaches around the API defined in AUDITED-TEST-API.md.

Flagged as violations (AST-based, consistent with the harness's
``_is_stub_impl`` approach — never regex):

* Calls to banned advancers/shortcuts (``game.run``, ``run_game``,
  ``run_turn``, the old free-function step helpers ``cast_spell`` /
  ``resolve_top`` / ``_resolve_top_of_stack``, ...).
* Direct card-internal probes (``on_resolve``, ``register_triggers``,
  ``get_targets``, ``get_cost_reduction``, ...) called from a test.
* Private-attribute poking — any attribute access with a leading underscore
  (``_script``, ``_resolve_targets``, ``_pop``, ``_omniscience_active``, ...).
* Any engine-touching call whose name is not in the AUDITED-TEST-API.md
  allow-list (curated ban list below).

NOT flagged: imports (the import-boundary decision permits importing the
engine under test for value types/enums — the rule constrains the API surface
used to *drive/observe*, not imports), plain attribute reads, and the bodies
of canonical card hooks (``on_resolve`` etc.) defined on fixture card classes
inside the test file — those are card-implementation code, not test-driver
code (calls *to* those hooks from test code are still flagged).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

# This file lives at <oracle_workspace>/tests/audited/test_api_conformance.py
_ORACLE_WORKSPACE = Path(__file__).resolve().parents[2]
_ORACLE_AUDITED = _ORACLE_WORKSPACE / "tests" / "audited"
# Canonical audited tree: benchmarks/sos/data/tests/audited
_CANONICAL_AUDITED = _ORACLE_WORKSPACE.parent / "tests" / "audited"


# ---------------------------------------------------------------------------
# The ban list — engine-touching names outside the AUDITED-TEST-API allow-list
# ---------------------------------------------------------------------------

_BANNED_CALLS: dict[str, str] = {
    # -- banned advancers / shortcuts -------------------------------------
    "run": "game.run() is prohibited — advance via priority_loop/advance_to_phase",
    "run_game": "run_game() is prohibited — advance via priority_loop/advance_to_phase",
    "run_turn": "run_turn() is prohibited — advance via priority_loop/advance_to_phase",
    "advance_phase": "raw phase stepping bypasses the sanctioned advancers",
    "cast_spell": "old step helper — cast via a CastSpell directive in priority_loop",
    "resolve_top": "old step helper — resolution happens inside priority_loop",
    "_resolve_top_of_stack": "old auto-drain helper — resolution happens inside priority_loop",
    "cast_spell_from_exile": "use CastSpell(..., from_zone=Zone.EXILE) instead",
    "cast_spell_free": "use a CastSpellFree directive instead",
    "cast_spell_for_cost": "alternative costs are driven through directives/choices",
    "play_land": "use a PlayLand directive instead",
    "activate_ability": "use an ActivateAbility directive instead",
    "declare_attackers": "combat declarations are choice-script answers via advance_to_phase",
    "declare_blockers": "combat declarations are choice-script answers via advance_to_phase",
    "declare_attackers_step": "combat steps run inside advance_to_phase",
    "declare_blockers_step": "combat steps run inside advance_to_phase",
    "combat_damage_step": "combat steps run inside advance_to_phase",
    "end_combat_step": "combat steps run inside advance_to_phase",
    # -- card-internal probes ---------------------------------------------
    "on_resolve": "card-internal probe — resolution happens via the driver",
    "on_cast": "card-internal probe — casting happens via directives",
    "can_cast": "card-internal probe — legality is asserted via perform_illegal_action",
    "get_targets": "card-internal probe — targets ride on directives / choices",
    "choose_targets": "card-internal probe",
    "register_triggers": "card-internal probe — registration happens via setup/zone changes",
    "register_replacement_effects": "card-internal probe",
    "get_cost_reduction": "card-internal probe — assert cost via mana-minimality",
    "cost_reduction": "card-internal probe — assert cost via mana-minimality",
    "get_activated_abilities": "card-internal probe — use ActivateAbility(printed index)",
    "get_loyalty_abilities": "card-internal probe — use ActivateAbility(printed index)",
    "get_mana_abilities": "card-internal probe — use ActivateAbility(printed index)",
    "get_modes": "card-internal probe",
    "apply_continuous_effect": "card-internal probe",
    "on_enchant": "card-internal probe",
    "on_detach": "card-internal probe",
    "end_of_turn_cleanup": "card-internal probe — cleanup runs via advance_to_phase",
    "on_leave_battlefield": "card-internal probe",
    "activate": "card-internal probe — use an ActivateAbility directive",
    # -- engine machinery / direct state mutation -------------------------
    "fire_event": "hand-fired events bypass the simulation",
    "register": "direct trigger/effect registration bypasses the simulation",
    "unregister": "direct trigger/effect registration bypasses the simulation",
    "apply_all": "effect-manager internals",
    "remove_expired": "effect-manager internals",
    "push": "direct stack mutation",
    "pop": "direct stack mutation",
    "peek": "direct stack inspection — use assert_stack/assert_on_stack",
    "popleft": "direct script-queue mutation",
    "appendleft": "direct script-queue mutation",
    "move_to_zone": "direct zone mutation — reach states via setup or gameplay",
    "move_zone": "direct zone mutation — reach states via setup or gameplay",
    "destroy": "direct state mutation",
    "sacrifice": "direct state mutation",
    "exile": "direct state mutation",
    "draw_card": "direct state mutation",
    "discard": "direct state mutation",
    "create_token": "direct state mutation",
    "add_counter": "direct state mutation — use PermanentSpec(counters=...)",
    "remove_counter": "direct state mutation",
    "tap": "direct state mutation — use PermanentSpec(tapped=True)",
    "untap": "direct state mutation",
    "deal_damage": "direct state mutation",
    "resolve_state_based_actions": "SBAs run inside the sanctioned advancers",
    "check_state_based_actions": "SBAs run inside the sanctioned advancers",
    "add": "direct zone/pool mutation — use set_board_state",
    "remove": "direct zone/pool mutation — use set_board_state",
    "shuffle": "direct zone mutation",
    "empty": "direct pool mutation",
    "pay": "direct pool mutation — payment happens inside the cast pipeline",
    "can_pay": "payment legality is asserted via perform_illegal_action",
    "add_restricted": "direct pool mutation",
    "get_all": "raw zone read — assert via the assert_* family",
    "setattr": "dynamic attribute poking",
    "delattr": "dynamic attribute poking",
    # -- player choice methods (driven by the engine, never called directly)
    "choose": "engine-prompted choice — script it on the choices channel",
    "choose_target": "engine-prompted choice — script it on the choices channel",
    "choose_yes_no": "engine-prompted choice — script it on the choices channel",
    "choose_card": "engine-prompted choice — script it on the choices channel",
    "assign_damage_order": "engine-prompted choice — script it on the choices channel",
    # -- engine machinery constructors ------------------------------------
    "StackObject": "engine machinery construction",
    "TriggerRegistration": "engine machinery construction",
    "ReplacementEffect": "engine machinery construction",
    "ActivatedAbilityInstance": "engine machinery construction",
    "LoyaltyAbilityInstance": "engine machinery construction",
    "ContinuousEffect": "engine machinery construction",
    "CombatState": "engine machinery construction",
    "ManaPool": "engine machinery construction",
    # -- old non-allow-list test_utils helpers ----------------------------
    "set_mana_pool": "outside the allow-list — use set_board_state(mana=...)",
    "set_hand": "outside the allow-list — use set_board_state(hand=...)",
    "set_battlefield": "outside the allow-list — use set_board_state(battlefield=...)",
    "set_library_top": "outside the allow-list — use set_board_state(library=...)",
    "set_graveyard": "outside the allow-list — use set_board_state(graveyard=...)",
    "assert_casting_error": "outside the allow-list — use perform_illegal_action",
    "card_colors": "outside the allow-list — assert mana_cost identity directly",
}

# Canonical card hooks: when *defined* on a fixture card class inside the test
# file, their bodies are card-implementation code and are exempt from the
# scan.  Calls to these names from test code are still violations.
_CARD_HOOK_METHODS = frozenset({
    "__init__",
    "on_resolve",
    "on_cast",
    "can_cast",
    "get_targets",
    "choose_targets",
    "register_triggers",
    "register_replacement_effects",
    "get_activated_abilities",
    "get_loyalty_abilities",
    "get_mana_abilities",
    "get_modes",
    "cost_reduction",
    "apply_continuous_effect",
    "end_of_turn_cleanup",
    "on_leave_battlefield",
})


@dataclass
class Violation:
    """One conformance violation at file:line."""

    file: Path
    line: int
    symbol: str
    reason: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.symbol} — {self.reason}"


def _call_name(node: ast.Call) -> str | None:
    """Return the simple name of a call target (Name or Attribute)."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _exempt_nodes(tree: ast.Module) -> set[int]:
    """Collect node ids inside fixture-card hook bodies (exempt from scan).

    A fixture card class is a non-``Test*`` class with at least one base
    (e.g. ``class QuickStudy(Instant)``).  Its canonical card hooks are card
    implementation code, equivalent to a ``card_impl.py``.
    """
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name.startswith("Test") or not node.bases:
            continue
        for item in node.body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name in _CARD_HOOK_METHODS
            ):
                for child in ast.walk(item):
                    exempt.add(id(child))
    return exempt


def check_file(path: Path) -> list[Violation]:
    """Scan one audited test file; return all conformance violations."""
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    exempt = _exempt_nodes(tree)

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if id(node) in exempt:
            continue

        # Private-attribute poking: any leading-underscore attribute access.
        # (``super().__init__`` in fixture-card classes is exempted above;
        # ``self._helper`` accesses the test class's own members, not an
        # engine/card/game object, and is permitted.)
        if isinstance(node, ast.Attribute):
            on_self = isinstance(node.value, ast.Name) and node.value.id == "self"
            if node.attr.startswith("_") and node.attr != "__init__" and not on_self:
                violations.append(
                    Violation(
                        file=path,
                        line=node.lineno,
                        symbol=node.attr,
                        reason="private-attribute poking on engine/card/game objects",
                    )
                )

        # Banned engine-touching calls.
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name is not None and name in _BANNED_CALLS:
                violations.append(
                    Violation(
                        file=path,
                        line=node.lineno,
                        symbol=name,
                        reason=_BANNED_CALLS[name],
                    )
                )

    return violations


def discover_audited_test_files() -> list[Path]:
    """Every Phase-18 audited ``sos_*/tests.py`` in both trees.

    The oracle workspace authoring tree defines the migrated set; the
    canonical copies of the same collector directories are scanned too so the
    two copies cannot drift apart in conformance.
    """
    files: list[Path] = []
    oracle_files = sorted(_ORACLE_AUDITED.glob("**/sos_*/tests.py"))
    files.extend(oracle_files)
    for oracle_file in oracle_files:
        rel = oracle_file.relative_to(_ORACLE_AUDITED)
        canonical = _CANONICAL_AUDITED / rel
        if canonical.exists():
            files.append(canonical)
    return files


def scan_audited_tests() -> list[Violation]:
    """Scan every discovered audited test file."""
    violations: list[Violation] = []
    for path in discover_audited_test_files():
        violations.extend(check_file(path))
    return violations


# ---------------------------------------------------------------------------
# The meta-tests
# ---------------------------------------------------------------------------


def test_audited_tests_use_only_the_test_api() -> None:
    """Every audited test file conforms to the AUDITED-TEST-API allow-list."""
    files = discover_audited_test_files()
    assert files, (
        f"No audited test files discovered under {_ORACLE_AUDITED} — "
        f"the conformance scan would be vacuous"
    )
    violations = scan_audited_tests()
    if violations:
        listing = "\n".join(str(v) for v in violations)
        raise AssertionError(
            f"{len(violations)} audited-test API violation(s):\n{listing}"
        )


_PLANTED_VIOLATION_FIXTURE = '''\
from test_utils import create_game
from engine.casting import cast_spell


def test_bad() -> None:
    game = create_game()
    game.run()                                # banned advancer
    cast_spell(game, game.players[0], None)   # old step helper
    resolve_top(game)                         # old step helper
    game.players[0]._script.appendleft(1)     # private poke (+ appendleft)
    card.on_resolve(game)                     # card-internal probe
'''

_CLEAN_FIXTURE = '''\
from test_utils import (
    CastSpell, DeterministicPlayer, PermanentSpec, Zone, assert_in_zone,
    assert_stack_empty, create_game, no_op, perform_action, priority_loop,
    set_board_state, set_player,
)
from engine.card import Instant
from engine.game import deal_damage
from engine.types import ManaType


class FixtureBolt(Instant):
    """Fixture card — hook bodies are card-impl code, exempt from the scan."""

    def on_resolve(self, game):
        targets = getattr(self, "chosen_targets", []) or []
        if targets:
            deal_damage(game, self, targets[0], 3)


def test_good() -> None:
    game = create_game(seed=1)
    set_board_state(game, 0, hand=[FixtureBolt(name="Bolt")],
                    battlefield=[PermanentSpec("Mountain", tapped=True)],
                    mana={ManaType.RED: 1})
    set_player(game, 0, DeterministicPlayer("P0", script=[
        perform_action(CastSpell("Bolt", targets=["Bear"])),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op(), no_op()]))
    priority_loop(game)
    assert_in_zone(game, 0, Zone.GRAVEYARD, "Bolt")
    assert_stack_empty(game)
'''


def test_checker_catches_planted_violations(tmp_path: Path) -> None:
    """The guard actually fires: a planted bad file is flagged on every count."""
    bad = tmp_path / "tests.py"
    bad.write_text(_PLANTED_VIOLATION_FIXTURE)
    violations = check_file(bad)
    symbols = {v.symbol for v in violations}
    for expected in ("run", "cast_spell", "resolve_top", "_script", "appendleft", "on_resolve"):
        assert expected in symbols, (
            f"Planted violation {expected!r} was NOT caught; "
            f"caught only: {sorted(symbols)}"
        )
    # Every violation carries a usable file:line pointer.
    assert all(v.line > 0 for v in violations)


def test_checker_passes_clean_canonical_shape(tmp_path: Path) -> None:
    """The canonical simulation-only shape produces zero violations."""
    good = tmp_path / "tests.py"
    good.write_text(_CLEAN_FIXTURE)
    assert check_file(good) == []
