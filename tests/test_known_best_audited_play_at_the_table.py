"""No Known-Best Audited Test drives the game by hand (ADR-018): none writes
the step, the active or priority player, the turn number or the step state,
and none calls the engine's own stepping. Play goes through the Test
Interface's ``run``. The FDN Audited Tests also place no card after
construction and use none of the ``test_utils`` drivers, which are the
Reference Tests' helpers; Audited Engine Tests that keep their old form for
now may still use those drivers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

AUDITED = Path(__file__).resolve().parents[1] / "known_best/data/tests/audited"
ENGINE_TESTS = AUDITED / "engine"
FDN_TESTS = AUDITED / "fdn"

LIFECYCLE = {"phase", "step", "active_player_index", "priority_player_index", "turn_number", "step_state"}
STEPPING = {
    "advance", "advance_phase", "advance_to_phase", "start_step", "run_turn", "run_game", "priority_loop",
    "untap_step", "_do_untap_step", "declare_attackers_step", "declare_blockers_step", "combat_damage_step",
    "end_combat_step", "_do_cleanup_step", "cleanup_iteration", "cleanup_mechanical", "resolve_top_of_stack",
    "open_window", "close_window",
}

PLACING_AND_DRIVING = {
    "set_board_state", "put_on_battlefield", "enter_permanent", "cast_card", "move_to_zone", "cast_spell_free",
    "cast_spell", "resolve_stack", "activate_card_ability", "activate_loyalty_ability", "declare_attackers",
    "declare_blockers", "run_scripts", "advance_game_to_phase", "finish_cleanup", "take_action",
}


def _hand_driving(path: Path, forbidden: set[str] = STEPPING) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            found += [
                f"line {t.lineno}: writes .{t.attr}"
                for target in targets for t in ast.walk(target)
                if isinstance(t, ast.Attribute) and t.attr in LIFECYCLE
            ]
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name in forbidden:
                found.append(f"line {node.lineno}: calls {name}()")
    return found


@pytest.mark.parametrize("path", sorted(ENGINE_TESTS.glob("test_*.py")), ids=lambda p: p.name)
def test_audited_engine_test_does_not_drive_the_game_by_hand(path: Path):
    assert _hand_driving(path) == []


@pytest.mark.parametrize(
    "path", sorted(FDN_TESTS.glob("*/tests.py")), ids=lambda p: p.parent.name
)
def test_fdn_audited_test_does_not_drive_the_game_by_hand(path: Path):
    assert _hand_driving(path, STEPPING | PLACING_AND_DRIVING) == []
