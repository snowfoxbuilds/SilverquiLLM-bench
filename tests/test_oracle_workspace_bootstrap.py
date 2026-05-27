"""Tests verifying the Test Oracle Workspace bootstrap (TODO item 1).

Checks:
- Directory structure mirrors workspace/ correctly
- All 10 audited card stubs exist
- test_utils.py exports required helper functions
- The validation harness exists and is importable
- Stub detection logic works correctly
- Empty stubs cause the harness to skip (exit 0)
"""

from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ORACLE_WORKSPACE = _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace"

# The 10 audited cards expected per TODO
_EXPECTED_CARDS = [
    "sos_1", "sos_4", "sos_13", "sos_57", "sos_97",
    "sos_120", "sos_201", "sos_226", "sos_245", "sos_257",
]

# Required helper functions in test_utils.py
_REQUIRED_HELPERS = [
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
]


class TestOracleWorkspaceStructure:
    """Verify the oracle workspace directory has the expected layout."""

    def test_workspace_root_exists(self) -> None:
        assert _ORACLE_WORKSPACE.is_dir(), (
            f"Oracle workspace not found at {_ORACLE_WORKSPACE}"
        )

    def test_engine_directory_exists(self) -> None:
        engine_dir = _ORACLE_WORKSPACE / "engine"
        assert engine_dir.is_dir(), "engine/ directory missing from oracle workspace"

    def test_cards_fdn_directory_exists(self) -> None:
        fdn_dir = _ORACLE_WORKSPACE / "cards" / "fdn"
        assert fdn_dir.is_dir(), "cards/fdn/ directory missing from oracle workspace"

    def test_cards_sos_directory_exists(self) -> None:
        sos_dir = _ORACLE_WORKSPACE / "cards" / "sos"
        assert sos_dir.is_dir(), "cards/sos/ directory missing from oracle workspace"

    def test_test_utils_exists(self) -> None:
        assert (_ORACLE_WORKSPACE / "test_utils.py").is_file(), (
            "test_utils.py missing from oracle workspace"
        )

    def test_agents_md_exists(self) -> None:
        assert (_ORACLE_WORKSPACE / "AGENTS.md").is_file(), (
            "AGENTS.md missing from oracle workspace"
        )

    def test_pytest_ini_exists(self) -> None:
        assert (_ORACLE_WORKSPACE / "pytest.ini").is_file(), (
            "pytest.ini missing from oracle workspace"
        )


class TestAuditedCardStubs:
    """Verify all 10 audited card stubs exist at expected paths."""

    @pytest.mark.parametrize("card_name", _EXPECTED_CARDS)
    def test_card_impl_exists(self, card_name: str) -> None:
        impl_path = _ORACLE_WORKSPACE / "cards" / "sos" / card_name / "card_impl.py"
        assert impl_path.is_file(), (
            f"card_impl.py not found for {card_name} at {impl_path}"
        )

    @pytest.mark.parametrize("card_name", _EXPECTED_CARDS)
    def test_card_impl_is_valid_python(self, card_name: str) -> None:
        """Each card_impl.py should be parseable Python."""
        impl_path = _ORACLE_WORKSPACE / "cards" / "sos" / card_name / "card_impl.py"
        if not impl_path.exists():
            pytest.skip(f"{card_name} impl not present")
        content = impl_path.read_text()
        # Should not raise SyntaxError
        ast.parse(content)


class TestTestUtilsHelpers:
    """Verify test_utils.py has all required helper functions."""

    @pytest.mark.parametrize("func_name", _REQUIRED_HELPERS)
    def test_helper_function_defined(self, func_name: str) -> None:
        """Each required helper must be defined as a callable in test_utils.py."""
        test_utils_path = _ORACLE_WORKSPACE / "test_utils.py"
        content = test_utils_path.read_text()
        tree = ast.parse(content)
        func_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert func_name in func_names, (
            f"Required helper '{func_name}' not found in test_utils.py. "
            f"Found: {sorted(func_names)}"
        )


class TestValidationHarness:
    """Verify the validation harness (test_audited_against_reference.py) exists and works."""

    def test_harness_file_exists(self) -> None:
        harness = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        assert harness.is_file(), "test_audited_against_reference.py not found in tests/"

    def test_harness_is_valid_python(self) -> None:
        harness = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        content = harness.read_text()
        ast.parse(content)

    def test_harness_can_be_collected_by_pytest(self) -> None:
        """pytest --collect-only should succeed on the harness file."""
        harness = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", str(harness)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=30,
        )
        # Should exit 0 (collected items) or 5 (no tests collected, all skipped)
        assert result.returncode in (0, 5), (
            f"pytest --collect-only failed with rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestStubDetection:
    """Verify the stub detection logic correctly identifies stubs vs real impls."""

    def test_stub_impl_is_detected_as_stub(self) -> None:
        """A card_impl.py with only `pass` in the class body should be a stub."""
        # Import the harness to test its _is_stub_impl function
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # All current card stubs should be detected as stubs
        for cn in _EXPECTED_CARDS:
            impl_path = _ORACLE_WORKSPACE / "cards" / "sos" / cn / "card_impl.py"
            if impl_path.exists():
                result = module._is_stub_impl(impl_path)
                assert result is True, (
                    f"{cn}/card_impl.py should be detected as stub but wasn't"
                )

    def test_nonexistent_impl_is_treated_as_stub(self) -> None:
        """A path that doesn't exist should be treated as a stub."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        fake_path = _ORACLE_WORKSPACE / "cards" / "sos" / "sos_9999" / "card_impl.py"
        assert module._is_stub_impl(fake_path) is True

    def test_real_impl_with_on_resolve_is_not_stub(self, tmp_path: Path) -> None:
        """A card_impl.py that defines on_resolve should NOT be a stub."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        impl_file = tmp_path / "card_impl.py"
        impl_file.write_text(
            "class Card:\n"
            "    def __init__(self):\n"
            "        self.name = 'Test Card'\n"
            "\n"
            "    def on_resolve(self, game_state):\n"
            "        game_state.draw(1)\n"
        )
        assert module._is_stub_impl(impl_file) is False

    def test_real_impl_with_can_cast_is_not_stub(self, tmp_path: Path) -> None:
        """A card_impl.py that defines can_cast should NOT be a stub."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        impl_file = tmp_path / "card_impl.py"
        impl_file.write_text(
            "class Card:\n"
            "    def __init__(self):\n"
            "        self.mana_cost = '{1}{W}'\n"
            "\n"
            "    def can_cast(self, player):\n"
            "        return player.mana >= 2\n"
        )
        assert module._is_stub_impl(impl_file) is False

    def test_impl_with_only_init_is_still_stub(self, tmp_path: Path) -> None:
        """A card_impl.py with only __init__ (no gameplay methods) IS a stub."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        impl_file = tmp_path / "card_impl.py"
        impl_file.write_text(
            "class Card:\n"
            "    def __init__(self):\n"
            "        self.name = 'Test Card'\n"
            "        self.mana_cost = '{2}{U}'\n"
        )
        assert module._is_stub_impl(impl_file) is True

    def test_discover_includes_non_stub_card(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_discover_oracle_cards() should include a card with a real impl."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Set up a fake oracle card directory with a real impl
        card_name = "sos_1"
        card_dir = tmp_path / "oracle" / "cards" / "sos" / card_name
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text(
            "class Card:\n"
            "    def on_resolve(self, game_state):\n"
            "        pass\n"
        )

        # Set up a matching audited test file
        audited_dir = tmp_path / "audited" / "sos" / card_name
        audited_dir.mkdir(parents=True)
        (audited_dir / "tests.py").write_text("def test_placeholder(): pass\n")

        # Monkeypatch the module-level paths used by _discover_oracle_cards
        monkeypatch.setattr(module, "_ORACLE_CARDS_DIR", tmp_path / "oracle" / "cards" / "sos")
        monkeypatch.setattr(module, "_AUDITED_DIR", tmp_path / "audited" / "sos")
        monkeypatch.setattr(module, "_AUDITED_CARDS", [card_name])

        cards = module._discover_oracle_cards()
        assert card_name in cards, (
            f"Expected {card_name} with real impl to be discovered, got: {cards}"
        )


class TestHarnessWithStubsExitsCleanly:
    """With only stub impls, the harness should exit 0 (all skipped)."""

    def test_harness_exits_zero_with_stubs_only(self) -> None:
        """Running the harness with no real oracle impls should pass (skip all)."""
        harness = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(harness), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
        )
        # Exit code 0 means passed (some skipped). Exit code 5 means no tests collected.
        # Both are acceptable for stubs-only state.
        assert result.returncode in (0, 5), (
            f"Harness should exit cleanly with stubs only but got rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_oracle_cards_discovered_with_stubs(self) -> None:
        """_discover_oracle_cards() should return empty list when all impls are stubs."""
        harness_path = _REPO_ROOT / "tests" / "test_audited_against_reference.py"
        spec = importlib.util.spec_from_file_location(
            "test_audited_against_reference", harness_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        cards = module._discover_oracle_cards()
        assert cards == [], (
            f"Expected no oracle cards with stubs only, got: {cards}"
        )
