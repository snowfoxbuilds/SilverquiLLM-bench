"""Tests for TODO item 4: event-type strings→classes migration completeness.

Verifies that no raw string event_type assignments remain in cards/fdn/ or
docs/specs/, and that the typed event class pattern is used correctly.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Repo root — two levels up from tests/
_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNoRawStringEventTypes:
    """Ensure event_type = 'some_string' patterns are fully eliminated."""

    def test_no_raw_string_event_types_in_cards_fdn(self) -> None:
        """grep -rn 'event_type *= *['\\'\"']' cards/fdn/ should return zero matches."""
        result = subprocess.run(
            ["grep", "-rn", r"event_type *= *['\"]", str(_REPO_ROOT / "cards" / "fdn")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Found raw string event_type in cards/fdn/:\n{result.stdout}"
        )

    def test_no_raw_string_event_types_in_docs_specs(self) -> None:
        """grep -rn 'event_type *= *['\\'\"']' docs/specs/ should return zero matches."""
        result = subprocess.run(
            ["grep", "-rn", r"event_type *= *['\"]", str(_REPO_ROOT / "docs" / "specs")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Found raw string event_type in docs/specs/:\n{result.stdout}"
        )


class TestFdn244UsesTypedEventClasses:
    """Verify cards/fdn/fdn_244/card_impl.py uses typed event classes."""

    @pytest.fixture()
    def card_impl_source(self) -> str:
        path = _REPO_ROOT / "cards" / "fdn" / "fdn_244" / "card_impl.py"
        assert path.exists(), f"Expected {path} to exist"
        return path.read_text(encoding="utf-8")

    def test_imports_event_class(self, card_impl_source: str) -> None:
        """Should import a typed event class from engine.events."""
        assert re.search(
            r"from engine\.events import .+Event", card_impl_source
        ), "fdn_244/card_impl.py should import a typed event class from engine.events"

    def test_imports_replacement_effect(self, card_impl_source: str) -> None:
        """Should import ReplacementEffect from engine.replacement_effects."""
        assert "from engine.replacement_effects import ReplacementEffect" in card_impl_source

    def test_registers_with_replacement_manager(self, card_impl_source: str) -> None:
        """Should use game.replacement_manager.register(), not game.register_replacement()."""
        assert "replacement_manager.register" in card_impl_source
        assert "game.register_replacement(" not in card_impl_source

    def test_event_type_is_class_reference(self, card_impl_source: str) -> None:
        """event_type= should reference a class, not a string literal."""
        # Find event_type= assignments — value should NOT be quoted
        matches = re.findall(r"event_type\s*=\s*(\S+)", card_impl_source)
        assert matches, "Should have at least one event_type= assignment"
        for value in matches:
            assert not value.startswith(("'", '"')), (
                f"event_type should be a class reference, not a string: {value}"
            )


class TestCardInterfaceSpecUsesTypedAPI:
    """Verify docs/specs/CARD-INTERFACE.md uses the new typed replacement API."""

    @pytest.fixture()
    def spec_source(self) -> str:
        path = _REPO_ROOT / "docs" / "specs" / "CARD-INTERFACE.md"
        assert path.exists(), f"Expected {path} to exist"
        return path.read_text(encoding="utf-8")

    def test_uses_replacement_manager_register(self, spec_source: str) -> None:
        """Should show game.replacement_manager.register() in examples."""
        assert "replacement_manager.register" in spec_source

    def test_does_not_use_old_register_replacement_api(self, spec_source: str) -> None:
        """Should NOT reference the old game.register_replacement() API."""
        assert "game.register_replacement(" not in spec_source

    def test_imports_typed_event_class(self, spec_source: str) -> None:
        """Should import a typed event class (ending in Event) from engine.events."""
        assert re.search(
            r"from engine\.events import \w+Event", spec_source
        ), "CARD-INTERFACE.md should show importing typed event classes"

    def test_event_type_references_class_not_string(self, spec_source: str) -> None:
        """In code examples, event_type= should reference a class, not a string."""
        matches = re.findall(r"event_type\s*=\s*(\S+)", spec_source)
        assert matches, "Should have event_type= in code examples"
        for value in matches:
            # Strip trailing comma if present
            clean = value.rstrip(",)")
            assert not clean.startswith(("'", '"')), (
                f"event_type in spec should be a class reference, not a string: {value}"
            )

    def test_uses_event_destination_mutation(self, spec_source: str) -> None:
        """Should demonstrate real replacement pattern: mutating event.destination."""
        assert "event.destination" in spec_source, (
            "CARD-INTERFACE.md replacement example should use event.destination "
            "mutation (the canonical replacement effect pattern)"
        )

    def test_does_not_use_nonexistent_game_exile(self, spec_source: str) -> None:
        """Should NOT use game.exile() as replacement logic — that API doesn't exist."""
        # game.exile() in modal examples is fine; but inside replacement callbacks it's wrong.
        # Check that the replacement effect example doesn't call game.exile()
        replacement_section = ""
        in_replacement = False
        for line in spec_source.splitlines():
            if "replacement" in line.lower() and "```python" in line.lower():
                in_replacement = True
            elif in_replacement and "```python" in line:
                in_replacement = True
            elif "### Replacement Effects" in line:
                in_replacement = True
            elif in_replacement and line.startswith("### ") and "Replacement" not in line:
                break
            if in_replacement:
                replacement_section += line + "\n"
        # The replacement section should not use game.exile() as the replacement mechanism
        assert "game.exile(" not in replacement_section, (
            "Replacement effect example should use event.destination mutation, "
            "not game.exile() which is not a real replacement pattern"
        )

    def test_replacement_callback_returns_event(self, spec_source: str) -> None:
        """Replacement callback should return the modified event object."""
        # The canonical pattern: def callback(...): ... return event
        assert re.search(
            r"return event", spec_source
        ), "Replacement callback should return the modified event object"
