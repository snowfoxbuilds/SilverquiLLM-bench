"""Bootstrap/readiness checks for legacy SOS and every selected HOB oracle."""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.oracle_support import OracleLayout, is_stub_impl, load_layout, readiness_errors

ROOT = Path(__file__).resolve().parents[1]
SOS_CARDS = (
    "sos_1",
    "sos_4",
    "sos_13",
    "sos_57",
    "sos_97",
    "sos_120",
    "sos_201",
    "sos_226",
    "sos_245",
    "sos_257",
)
HELPERS = {
    "sos": (
        "set_mana_pool",
        "set_hand",
        "set_battlefield",
        "set_library_top",
        "set_graveyard",
        "assert_on_stack",
        "assert_in_zone",
        "assert_casting_error",
        "resolve_top",
        "cast_spell_from_exile",
    ),
    "hob-medium": (
        "create_game",
        "set_board_state",
        "cast_spell",
        "activate_card_ability",
        "advance_game_to_phase",
        "enter_permanent",
    ),
}


@pytest.fixture(params=("sos", "hob-medium"))
def layout(request):
    return load_layout(ROOT, request.param)


def test_workspace_shape(layout):
    for relative in (
        "engine",
        "cards/fdn",
        f"cards/{layout.target_set}",
        "test_utils.py",
        "AGENTS.md",
        "pytest.ini",
    ):
        assert (layout.oracle / relative).exists(), str(layout.oracle / relative)


def test_expected_oracles_are_present_and_parse(layout):
    cards = SOS_CARDS if layout.benchmark == "sos" else layout.cards
    assert cards
    for card in cards:
        path = layout.implementation(card)
        assert path.is_file(), f"Missing oracle implementation: {path}"
        ast.parse(path.read_text())
        if layout.benchmark == "hob-medium":
            assert not readiness_errors(layout, card)


def test_host_helper_surface(layout):
    tree = ast.parse((layout.oracle / "test_utils.py").read_text())
    names = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(HELPERS[layout.benchmark]) <= names


def test_reference_harness_collects_all_hob_cards():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            str(ROOT / "tests/test_audited_against_reference.py"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for card in load_layout(ROOT, "hob-medium", require_cards=True).cards:
        assert f"hob-medium/{card}" in result.stdout


@pytest.mark.parametrize(
    "source,stub",
    [
        ("class Card:\n    def __init__(self): self.name = 'stub'\n", True),
        ("class Card:\n    def on_resolve(self, game): pass\n", False),
        ("class Card:\n    def can_cast(self, game): return True\n", False),
        ("class Broken(:", True),
    ],
)
def test_stub_detection(source, stub, tmp_path):
    path = tmp_path / "card_impl.py"
    path.write_text(source)
    assert is_stub_impl(path) is stub


def test_missing_impl_is_a_stub(tmp_path):
    assert is_stub_impl(tmp_path / "missing.py")


def test_hob_readiness_reports_missing_stub_and_empty_suite(tmp_path):
    selected = OracleLayout(tmp_path, "hob-medium", "hob", ("hob_12",))
    errors = readiness_errors(selected, "hob_12")
    assert any("missing oracle" in error for error in errors)
    assert any("missing audited" in error for error in errors)
    impl = selected.implementation("hob_12")
    suite = selected.suite("hob_12")
    impl.parent.mkdir(parents=True)
    suite.parent.mkdir(parents=True)
    impl.write_text("class Card:\n    def __init__(self): pass\n")
    suite.write_text("# no collected tests\n")
    errors = readiness_errors(selected, "hob_12")
    assert any("stub" in error for error in errors)
    assert any("empty audited" in error for error in errors)


def test_historical_sos_discovery_still_ignores_unimplemented_slots(tmp_path, monkeypatch):
    path = ROOT / "tests/test_audited_against_reference.py"
    spec = importlib.util.spec_from_file_location("oracle_reference_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_ORACLE_CARDS_DIR", tmp_path / "cards")
    monkeypatch.setattr(module, "_AUDITED_DIR", tmp_path / "audited")
    monkeypatch.setattr(module, "_AUDITED_CARDS", ["sos_1"])
    assert module._discover_oracle_cards() == []
    impl = tmp_path / "cards/sos_1/card_impl.py"
    suite = tmp_path / "audited/sos_1/tests.py"
    impl.parent.mkdir(parents=True)
    suite.parent.mkdir(parents=True)
    impl.write_text("class Card:\n    def on_resolve(self, game): pass\n")
    suite.write_text("def test_behavior(): assert True\n")
    assert module._discover_oracle_cards() == ["sos_1"]
