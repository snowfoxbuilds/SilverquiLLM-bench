"""Tests for silverquillm.workspace — workspace staging."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

from silverquillm.workspace import stage_workspace


@pytest.fixture()
def repo_root() -> Path:
    """Return the repository root (two levels up from this test file)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture()
def engine_dir(repo_root: Path) -> Path:
    return repo_root / "engine"


@pytest.fixture()
def staged(tmp_path: Path):
    """Run stage_workspace with new signature and return (workspace, output) paths."""
    return stage_workspace(tmp_path)


# ------------------------------------------------------------------
# Signature — cards_dir / engine_dir must NOT be accepted
# ------------------------------------------------------------------


class TestStageWorkspaceSignature:
    """stage_workspace must only accept output_dir and card_filter."""

    def test_signature_has_output_dir_as_first_positional(self):
        sig = inspect.signature(stage_workspace)
        params = list(sig.parameters.keys())
        assert params[0] == "output_dir"

    def test_signature_does_not_accept_cards_dir(self):
        sig = inspect.signature(stage_workspace)
        assert "cards_dir" not in sig.parameters

    def test_signature_does_not_accept_engine_dir(self):
        sig = inspect.signature(stage_workspace)
        assert "engine_dir" not in sig.parameters

    def test_signature_accepts_card_filter_keyword(self):
        sig = inspect.signature(stage_workspace)
        assert "card_filter" in sig.parameters
        param = sig.parameters["card_filter"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY

    def test_callable_with_just_output_dir(self, tmp_path):
        """stage_workspace(output_dir) should work without extra args."""
        ws, out = stage_workspace(tmp_path)
        assert ws.exists()
        assert out.exists()


# ------------------------------------------------------------------
# Basic structure
# ------------------------------------------------------------------


class TestWorkspaceStructure:
    """Verify the staged directory tree matches the spec."""

    def test_returns_two_paths(self, staged):
        workspace, output = staged
        assert workspace.exists()
        assert output.exists()

    def test_workspace_is_named_workspace(self, staged):
        workspace, _ = staged
        assert workspace.name == "workspace"

    def test_output_is_named_output(self, staged):
        _, output = staged
        assert output.name == "output"

    def test_prompt_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "prompt.md").is_file()

    def test_prompt_md_mentions_sos(self, staged):
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "/workspace/cards/sos/" in text

    def test_prompt_md_mentions_fdn(self, staged):
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "/workspace/cards/fdn/" in text

    def test_rulebook_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "rulebook.md").is_file()

    def test_engine_api_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "engine_api.md").is_file()

    def test_base_classes_py_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "base_classes.py").is_file()

    def test_test_utils_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "test_utils.md").is_file()

    def test_engine_directory_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "engine").is_dir()

    #def test_cards_fdn_directory_exists(self, staged):
    #    workspace, _ = staged
    #    assert (workspace / "cards" / "fdn").is_dir()

    def test_cards_sos_directory_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "cards" / "sos").is_dir()


# ------------------------------------------------------------------
# Engine copy
# ------------------------------------------------------------------


class TestEngineCopy:
    """Engine source should be a complete copy."""

    def test_engine_has_card_py(self, staged):
        workspace, _ = staged
        assert (workspace / "engine" / "card.py").is_file()

    def test_engine_has_game_py(self, staged):
        workspace, _ = staged
        assert (workspace / "engine" / "game.py").is_file()

    def test_engine_no_pycache(self, staged):
        workspace, _ = staged
        pycache = workspace / "engine" / "__pycache__"
        assert not pycache.exists()

    def test_engine_file_count_matches(self, staged, engine_dir):
        workspace, _ = staged
        src_files = {
            f.name
            for f in engine_dir.rglob("*.py")
            if "__pycache__" not in str(f)
        }
        staged_files = {
            f.name for f in (workspace / "engine").rglob("*.py")
        }
        assert src_files == staged_files


# ------------------------------------------------------------------
# FDN cards — filled implementations
# ------------------------------------------------------------------

"""
class TestFdnCards:

    def test_at_least_one_fdn_card(self, staged):
        workspace, _ = staged
        fdn_cards = list((workspace / "cards" / "fdn").iterdir())
        assert len(fdn_cards) > 0

    def test_fdn_cards_have_spec(self, staged):
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "fdn").iterdir():
            if card_dir.is_dir():
                assert (card_dir / "card_spec.json").is_file(), (
                    f"Missing card_spec.json in {card_dir.name}"
                )

    def test_fdn_cards_have_impl(self, staged):
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "fdn").iterdir():
            if card_dir.is_dir():
                assert (card_dir / "card_impl.py").is_file(), (
                    f"Missing card_impl.py in {card_dir.name}"
                )

    def test_fdn_impls_are_non_empty(self, staged):
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "fdn").iterdir():
            if card_dir.is_dir():
                impl = card_dir / "card_impl.py"
                if impl.exists():
                    content = impl.read_text()
                    assert len(content.strip()) > 0, (
                        f"Empty card_impl.py in fdn/{card_dir.name}"
                    )

    def test_fdn_spec_is_valid_json(self, staged):
        workspace, _ = staged
        some_card = next((workspace / "cards" / "fdn").iterdir())
        data = json.loads((some_card / "card_spec.json").read_text())
        assert "name" in data
"""

# ------------------------------------------------------------------
# SOS cards — templates
# ------------------------------------------------------------------


class TestSosCards:
    """SOS cards should be copied as templates."""

    def test_at_least_one_sos_card(self, staged):
        workspace, _ = staged
        sos_cards = list((workspace / "cards" / "sos").iterdir())
        assert len(sos_cards) > 0

    def test_sos_cards_have_spec(self, staged):
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "sos").iterdir():
            if card_dir.is_dir():
                assert (card_dir / "card_spec.json").is_file(), (
                    f"Missing card_spec.json in {card_dir.name}"
                )

    def test_sos_cards_have_impl(self, staged):
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "sos").iterdir():
            if card_dir.is_dir():
                assert (card_dir / "card_impl.py").is_file(), (
                    f"Missing card_impl.py in {card_dir.name}"
                )

    def test_sos_impls_are_templates(self, staged):
        """SOS card_impl.py files should be templates (contain pass or raise NotImplementedError)."""
        workspace, _ = staged
        for card_dir in (workspace / "cards" / "sos").iterdir():
            if card_dir.is_dir():
                impl = card_dir / "card_impl.py"
                if impl.exists():
                    content = impl.read_text()
                    # Templates typically have pass/raise/TODO markers
                    is_template = (
                        "pass" in content
                        or "NotImplementedError" in content
                        or "TODO" in content
                        or "..." in content
                    )
                    assert is_template, (
                        f"SOS card_impl.py in {card_dir.name} doesn't look like a template"
                    )

    def test_sos_spec_is_valid_json(self, staged):
        workspace, _ = staged
        some_card = next((workspace / "cards" / "sos").iterdir())
        data = json.loads((some_card / "card_spec.json").read_text())
        assert "name" in data


# ------------------------------------------------------------------
# Reference docs content
# ------------------------------------------------------------------


class TestReferenceDocs:
    """Reference docs should have meaningful content."""

    def test_engine_api_has_content(self, staged):
        workspace, _ = staged
        text = (workspace / "engine_api.md").read_text()
        assert len(text) > 50

    def test_test_utils_has_content(self, staged):
        workspace, _ = staged
        text = (workspace / "test_utils.md").read_text()
        assert len(text) > 50

    def test_base_classes_is_card_py(self, staged, engine_dir):
        """base_classes.py should be a copy of engine/card.py."""
        workspace, _ = staged
        original = (engine_dir / "card.py").read_text()
        staged_copy = (workspace / "base_classes.py").read_text()
        assert staged_copy == original


# ------------------------------------------------------------------
# Idempotency
# ------------------------------------------------------------------


class TestOutputDirectory:
    """Output directory should exist and be empty."""

    def test_output_is_empty(self, staged):
        _, output = staged
        assert list(output.iterdir()) == []

    def test_output_is_directory(self, staged):
        _, output = staged
        assert output.is_dir()


# ------------------------------------------------------------------
# Idempotency
# ------------------------------------------------------------------


class TestIdempotency:
    """Calling stage_workspace twice should not fail."""

    def test_can_restage(self, tmp_path):
        ws1, out1 = stage_workspace(tmp_path)
        ws2, out2 = stage_workspace(tmp_path)
        assert ws1 == ws2
        assert out1 == out2
        assert ws2.exists()

    def test_independent_copies_with_different_output_dirs(self, tmp_path):
        """Two calls with different output dirs create independent workspaces."""
        dir1 = tmp_path / "run1"
        dir1.mkdir()
        dir2 = tmp_path / "run2"
        dir2.mkdir()
        ws1, out1 = stage_workspace(dir1)
        ws2, out2 = stage_workspace(dir2)
        assert ws1 != ws2
        assert out1 != out2
        assert ws1.exists()
        assert ws2.exists()
        # Modifying one doesn't affect the other
        (ws1 / "prompt.md").write_text("modified")
        assert (ws2 / "prompt.md").read_text() != "modified"
