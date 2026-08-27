"""Tests for replay-validate CLI wiring: command registration and workspace/
card-set resolution.

These exercise only the resolution helpers and command registration — they do
NOT import a workspace's engine/cards (which would conflict with the SOS binding
the root suite uses), so they stay in-process.
"""

from __future__ import annotations

import click
import pytest

from silverquillm.replay.cli import _resolve_card_set, _resolve_workspace


def test_validate_registered_in_main_cli() -> None:
    """`benchmark validate` is reachable from the top-level CLI group."""
    from silverquillm.cli import main

    assert "validate" in main.commands


# ---------------------------------------------------------------------------
# _resolve_workspace
# ---------------------------------------------------------------------------

def test_resolve_workspace_explicit_overrides_benchmark(tmp_path) -> None:
    """An explicit --workspace wins over --benchmark."""
    assert _resolve_workspace("hob-medium", str(tmp_path)) == tmp_path.resolve()


def test_resolve_workspace_none_when_neither_given() -> None:
    assert _resolve_workspace(None, None) is None


def test_resolve_workspace_missing_explicit_raises(tmp_path) -> None:
    with pytest.raises(click.ClickException):
        _resolve_workspace(None, str(tmp_path / "does-not-exist"))


# (unknown-benchmark / hob-medium-resolution are covered in test_replay_v2_protocol.py)


# ---------------------------------------------------------------------------
# _resolve_card_set
# ---------------------------------------------------------------------------

def test_card_set_defaults_to_fdn_for_hob_medium(tmp_path) -> None:
    (tmp_path / "cards" / "fdn").mkdir(parents=True)
    assert _resolve_card_set("hob-medium", None, tmp_path) == "fdn"


def test_card_set_explicit_wins(tmp_path) -> None:
    (tmp_path / "cards" / "hob").mkdir(parents=True)
    assert _resolve_card_set("hob-medium", "hob", tmp_path) == "hob"


def test_card_set_none_for_sos(tmp_path) -> None:
    """SOS gets no registry (preserves the frozen scripted-player path)."""
    assert _resolve_card_set("sos", None, tmp_path) is None


def test_card_set_missing_dir_raises(tmp_path) -> None:
    """A resolved set with no matching cards/<set> dir is an error."""
    with pytest.raises(click.ClickException):
        _resolve_card_set("hob-medium", None, tmp_path)  # no cards/fdn under tmp_path
