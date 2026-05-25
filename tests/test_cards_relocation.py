"""Tests verifying cards/ relocation to benchmarks/sos/workspace/cards/ and SOS stub normalization."""

from __future__ import annotations

import importlib
import inspect
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestCardsRelocation:
    """Verify the structural move of cards/ was completed correctly."""

    def test_old_cards_directory_does_not_exist(self) -> None:
        """The top-level cards/ directory must no longer exist."""
        old_cards = REPO_ROOT / "cards"
        assert not old_cards.exists(), (
            f"Old cards/ directory still exists at {old_cards}"
        )

    def test_new_cards_directory_exists(self) -> None:
        """The cards package must exist at benchmarks/sos/workspace/cards/."""
        new_cards = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards"
        assert new_cards.is_dir(), f"Cards directory not found at {new_cards}"

    def test_cards_contains_fdn_subdirectory(self) -> None:
        """benchmarks/sos/workspace/cards/ must contain fdn/ subdirectory."""
        fdn_dir = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "fdn"
        assert fdn_dir.is_dir(), f"fdn/ subdirectory not found at {fdn_dir}"

    def test_cards_contains_sos_subdirectory(self) -> None:
        """benchmarks/sos/workspace/cards/ must contain sos/ subdirectory."""
        sos_dir = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos"
        assert sos_dir.is_dir(), f"sos/ subdirectory not found at {sos_dir}"

    def test_no_stale_cards_imports_outside_cards_package(self) -> None:
        """No .py file should use the legacy ``benchmarks.sos.workspace.cards`` prefix.

        Flat ``from cards.X import …`` is canonical after Option A.
        """
        result = subprocess.run(
            [
                "grep",
                "-rln",
                "--include=*.py",
                "-P",
                r"benchmarks\.sos\.workspace\.cards",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        from pathlib import Path
        docker_dir = str(REPO_ROOT / "docker")
        venv_dir = str(REPO_ROOT / "venv")
        self_path = str(Path(__file__).resolve())
        stale_files = [
            f
            for f in result.stdout.strip().splitlines()
            if f and not f.startswith(docker_dir)
            and not f.startswith(venv_dir)
            and f != self_path
        ]
        assert stale_files == [], (
            f"Legacy benchmarks.sos.workspace.cards references found:\n"
            + "\n".join(stale_files)
        )


# Sample of SOS card modules to test — includes the normalized stubs plus others
_SAMPLE_SOS_CARDS = [
    "sos_195",
    "sos_217",
    "sos_218",
]

# Specifically normalized stubs
_NORMALIZED_STUBS = ["sos_195", "sos_217", "sos_218"]


class TestSOSCardImplModules:
    """Parametrized tests for SOS card_impl module imports."""

    @pytest.mark.parametrize("card_id", _SAMPLE_SOS_CARDS)
    def test_card_impl_defines_cardimpl_subclass(self, card_id: str) -> None:
        """Each SOS card_impl module must define at least one class inheriting from CardImpl."""
        from engine.card import CardImpl

        module_path = f"cards.sos.{card_id}.card_impl"
        mod = importlib.import_module(module_path)

        # Find classes that inherit from CardImpl
        card_classes = [
            cls
            for name, cls in inspect.getmembers(mod, inspect.isclass)
            if issubclass(cls, CardImpl) and cls is not CardImpl
        ]
        assert len(card_classes) >= 1, (
            f"Module {module_path} does not define any class inheriting from CardImpl. "
            f"Found classes: {[name for name, _ in inspect.getmembers(mod, inspect.isclass)]}"
        )

    @pytest.mark.parametrize("card_id", _NORMALIZED_STUBS)
    def test_normalized_stub_has_proper_class_declaration(self, card_id: str) -> None:
        """Normalized stubs must have a proper class declaration, not just a docstring."""
        card_impl_path = (
            REPO_ROOT
            / "benchmarks"
            / "sos"
            / "workspace"
            / "cards"
            / "sos"
            / card_id
            / "card_impl.py"
        )
        assert card_impl_path.is_file(), f"card_impl.py not found at {card_impl_path}"

        content = card_impl_path.read_text()
        # Must contain a class declaration (not just a docstring or pass)
        assert "class " in content, (
            f"Normalized stub {card_id}/card_impl.py does not contain a class declaration"
        )
        # Must not be ONLY a docstring (should have class keyword)
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        class_lines = [l for l in lines if l.startswith("class ")]
        assert len(class_lines) >= 1, (
            f"Normalized stub {card_id}/card_impl.py has no proper class declarations"
        )
