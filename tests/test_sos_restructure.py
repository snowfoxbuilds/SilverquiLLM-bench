"""Tests for TODO item 3: SOS card restructure to unified cards/ layout.

Verifies:
- cards/sos/ directory exists with expected subdirectories
- Total card count is at least 271 SOS cards
- card_impl.py templates compile as valid Python (py_compile)
- card_impl.py templates produce a CardImpl subclass when executed
- Each card directory has card_spec.json + card_impl.py
- card_spec.json is valid JSON with required fields
- collector_number in spec matches directory name
- card_impl.py is a template with CardImpl subclass
- Old location benchmarks/sos/cards/ has no card subdirectories
"""

from __future__ import annotations

import importlib.util
import json
import py_compile
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CARDS_SOS = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos"
OLD_CARDS = REPO_ROOT / "benchmarks" / "sos" / "cards"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_card_subdirs() -> list[Path]:
    """Return all immediate subdirectories of cards/sos/ (excluding __pycache__)."""
    if not CARDS_SOS.is_dir():
        return []
    return sorted(
        p for p in CARDS_SOS.iterdir()
        if p.is_dir() and p.name != "__pycache__"
    )


# ---------------------------------------------------------------------------
# 1. Directory structure
# ---------------------------------------------------------------------------

class TestDirectoryStructure:
    def test_cards_sos_directory_exists(self):
        assert CARDS_SOS.is_dir(), f"Expected {CARDS_SOS} to be a directory"

    def test_cards_sos_has_subdirectories(self):
        subdirs = _get_card_subdirs()
        assert len(subdirs) > 0, "cards/sos/ should contain card subdirectories"


# ---------------------------------------------------------------------------
# 2. Card count
# ---------------------------------------------------------------------------

class TestCardCount:
    def test_at_least_340_card_directories(self):
        subdirs = _get_card_subdirs()
        assert len(subdirs) >= 340, (
            f"Expected at least 340 card directories, found {len(subdirs)}"
        )

    def test_exactly_271_base_sos_cards(self):
        """Base SOS cards use sos_N prefix (e.g. sos_1 through sos_271)."""
        base_dirs = [
            p for p in _get_card_subdirs()
            if p.name.startswith("sos_") and p.name[4:].isdigit()
        ]
        assert len(base_dirs) == 271, (
            f"Expected 271 base SOS card dirs, found {len(base_dirs)}"
        )




# ---------------------------------------------------------------------------
# 5. Both files present in each card directory
# ---------------------------------------------------------------------------

class TestBothFilesPresent:
    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_spec_json_exists(self, dirname):
        f = CARDS_SOS / dirname / "card_spec.json"
        assert f.is_file(), f"Expected {f} to exist"

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_impl_py_exists(self, dirname):
        f = CARDS_SOS / dirname / "card_impl.py"
        assert f.is_file(), f"Expected {f} to exist"

    def test_all_card_dirs_have_both_files(self):
        """Every card subdirectory must contain both card_spec.json and card_impl.py."""
        missing = []
        for d in _get_card_subdirs():
            for fname in ("card_spec.json", "card_impl.py"):
                if not (d / fname).is_file():
                    missing.append(str(d / fname))
        assert not missing, f"Missing files:\n" + "\n".join(missing[:20])


# ---------------------------------------------------------------------------
# 6. card_spec.json validity
# ---------------------------------------------------------------------------

class TestCardSpecValidity:
    @pytest.mark.parametrize("dirname", ["sos_1", "sos_50", "sos_271"])
    def test_card_spec_is_valid_json(self, dirname):
        spec_path = CARDS_SOS / dirname / "card_spec.json"
        data = json.loads(spec_path.read_text())
        assert isinstance(data, dict)

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_50", "sos_271"])
    def test_card_spec_has_required_fields(self, dirname):
        spec_path = CARDS_SOS / dirname / "card_spec.json"
        data = json.loads(spec_path.read_text())
        assert data.get("name"), f"'name' should be non-empty in {dirname}"
        assert data.get("collector_number"), f"'collector_number' should be non-empty in {dirname}"

    @pytest.mark.parametrize(
        "dirname,expected_cn",
        [
            ("sos_1", "1"),
            ("sos_271", "271"),
        ],
    )
    def test_collector_number_matches_directory(self, dirname, expected_cn):
        spec_path = CARDS_SOS / dirname / "card_spec.json"
        data = json.loads(spec_path.read_text())
        assert str(data["collector_number"]) == expected_cn, (
            f"collector_number {data['collector_number']} doesn't match expected {expected_cn} for dir {dirname}"
        )

    @pytest.mark.parametrize(
        "dirname,expected_set",
        [
            ("sos_1", "sos"),
        ],
    )
    def test_set_code_matches_card_type(self, dirname, expected_set):
        spec_path = CARDS_SOS / dirname / "card_spec.json"
        data = json.loads(spec_path.read_text())
        assert data.get("set_code") == expected_set, (
            f"set_code should be '{expected_set}' for {dirname}, got '{data.get('set_code')}'"
        )


# ---------------------------------------------------------------------------
# 7. card_impl.py is a template with CardImpl subclass
# ---------------------------------------------------------------------------

class TestCardImplTemplate:
    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_impl_contains_cardimpl_subclass(self, dirname):
        impl_path = CARDS_SOS / dirname / "card_impl.py"
        content = impl_path.read_text()
        assert "CardImpl" in content, (
            f"card_impl.py in {dirname} should reference CardImpl"
        )

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_impl_has_class_definition(self, dirname):
        impl_path = CARDS_SOS / dirname / "card_impl.py"
        content = impl_path.read_text()
        assert "class " in content, (
            f"card_impl.py in {dirname} should contain a class definition"
        )

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_impl_is_skeleton_template(self, dirname):
        """Template card_impl.py should have 'pass' (skeleton/stub)."""
        impl_path = CARDS_SOS / dirname / "card_impl.py"
        content = impl_path.read_text()
        assert "pass" in content, (
            f"card_impl.py in {dirname} should be a template with 'pass'"
        )



# ---------------------------------------------------------------------------
# 9. card_impl.py compiles as valid Python (syntax check)
# ---------------------------------------------------------------------------

class TestCardImplCompiles:
    """Use py_compile to verify card_impl.py templates are syntactically valid."""

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_card_impl_compiles_with_py_compile(self, dirname):
        impl_path = CARDS_SOS / dirname / "card_impl.py"
        # py_compile.compile raises py_compile.PyCompileError on syntax errors
        py_compile.compile(str(impl_path), doraise=True)


# ---------------------------------------------------------------------------
# 10. card_impl.py produces a usable CardImpl subclass when executed
# ---------------------------------------------------------------------------

class TestCardImplImportable:
    """Import card_impl.py modules and verify they define a CardImpl subclass."""

    @staticmethod
    def _load_card_impl(dirname: str) -> types.ModuleType:
        """Load a card_impl.py with a stub CardImpl base class injected."""
        impl_path = CARDS_SOS / dirname / "card_impl.py"

        # Create a stub base class that the template can inherit from
        class _StubCardImpl:
            pass

        # Load the module via importlib
        spec = importlib.util.spec_from_file_location(
            f"_sos_tmp_{dirname}_card_impl", impl_path
        )
        mod = importlib.util.module_from_spec(spec)
        # Inject the stub CardImpl into the module namespace so `class X(CardImpl)` works
        mod.CardImpl = _StubCardImpl  # type: ignore[attr-defined]
        spec.loader.exec_module(mod)
        return mod

    @pytest.mark.parametrize(
        "dirname,expected_class",
        [
            ("sos_1", None),    # any subclass is fine for base SOS
            ("sos_100", None),  # mid-range base SOS
            ("sos_271", None),  # last base SOS
        ],
    )
    def test_module_defines_cardimpl_subclass(self, dirname, expected_class):
        mod = self._load_card_impl(dirname)
        # Find all classes in the module that inherit from the stub CardImpl
        card_classes = [
            obj for name, obj in vars(mod).items()
            if isinstance(obj, type)
            and issubclass(obj, mod.CardImpl)  # type: ignore[attr-defined]
            and obj is not mod.CardImpl  # type: ignore[attr-defined]
        ]
        assert len(card_classes) >= 1, (
            f"card_impl.py in {dirname} should define at least one CardImpl subclass, "
            f"found classes: {[name for name, obj in vars(mod).items() if isinstance(obj, type)]}"
        )

    @pytest.mark.parametrize("dirname", ["sos_1", "sos_100", "sos_271"])
    def test_subclass_is_a_class(self, dirname):
        """The CardImpl subclass should be a proper class (not a function or other type)."""
        mod = self._load_card_impl(dirname)
        card_classes = [
            obj for name, obj in vars(mod).items()
            if isinstance(obj, type)
            and issubclass(obj, mod.CardImpl)  # type: ignore[attr-defined]
            and obj is not mod.CardImpl  # type: ignore[attr-defined]
        ]
        for cls in card_classes:
            assert isinstance(cls, type), f"{cls} should be a class"
