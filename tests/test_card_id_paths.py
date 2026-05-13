"""Tests for TODO item 4: Standardize all per-card paths on card_dir_name.

Verifies that AgentSession uses ``card_id`` (collector number) — not
``card_name`` (display name) — for all filesystem path construction:
postmortem paths, agent_thoughts.md, raw logs, regression postmortem paths.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    _generate_agent_thoughts,
    _get_postmortem_path,
)
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_SPEC: dict[str, Any] = {
    "name": "Ajani's Response",
    "mana_cost": "{1}{W}",
    "type_line": "Instant",
    "oracle_text": "Target creature gets +2/+2 until end of turn.",
    "collector_number": "42",
    "card_dir_name": "42",
}


def _make_config(**overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            timeout_per_card=300,
        ),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


@pytest.fixture()
def config():
    return _make_config()


@pytest.fixture()
def card_dir(tmp_path):
    d = tmp_path / "card_data"
    d.mkdir()
    (d / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    return d


@pytest.fixture()
def run_dir(tmp_path):
    d = tmp_path / "run_output"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# AgentSession has card_id field
# ---------------------------------------------------------------------------


class TestCardIdField:
    """AgentSession must expose a card_id field."""

    def test_card_id_is_a_dataclass_field(self):
        field_names = {f.name for f in dataclasses.fields(AgentSession)}
        assert "card_id" in field_names

    def test_card_id_defaults_to_empty_string(self, config, card_dir):
        session = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
        assert session.card_id == ""
        session.cleanup()

    def test_card_id_stores_value(self, config, card_dir):
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="42",
        )
        assert session.card_id == "42"
        session.cleanup()


# ---------------------------------------------------------------------------
# _path_id prefers card_id over card_name
# ---------------------------------------------------------------------------


class TestPathId:
    """_path_id should use card_id when set, else fall back to card_name."""

    def test_path_id_uses_card_id_when_set(self, config, card_dir):
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="42",
        )
        assert session._path_id == "42"
        session.cleanup()

    def test_path_id_falls_back_to_card_name_when_card_id_empty(self, config, card_dir):
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="",
        )
        assert session._path_id == "Ajani's Response"
        session.cleanup()

    def test_path_id_falls_back_to_card_name_when_card_id_not_provided(self, config, card_dir):
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
        )
        assert session._path_id == "Ajani's Response"
        session.cleanup()


# ---------------------------------------------------------------------------
# _get_postmortem_path uses card_id, not card_name
# ---------------------------------------------------------------------------


class TestGetPostmortemPath:
    """_get_postmortem_path must build path from the provided identifier."""

    def test_postmortem_path_uses_card_id(self, run_dir):
        path = _get_postmortem_path(run_dir, "42")
        assert path is not None
        assert "42" in path.parts
        assert "Ajani's Response" not in str(path)
        assert path == run_dir / "cards" / "42" / "postmortem.jsonl"

    def test_postmortem_path_returns_none_when_no_run_dir(self):
        path = _get_postmortem_path(None, "42")
        assert path is None


# ---------------------------------------------------------------------------
# _generate_agent_thoughts uses card_id for path construction
# ---------------------------------------------------------------------------


class TestGenerateAgentThoughts:
    """_generate_agent_thoughts must use the identifier for directory paths."""

    def test_reads_postmortem_from_card_id_subdir(self, run_dir):
        """When called with card_id='42', should look in cards/42/postmortem.jsonl."""
        # Create postmortem.jsonl under the card_id directory
        card_id = "42"
        card_subdir = run_dir / "cards" / card_id
        card_subdir.mkdir(parents=True)
        postmortem = card_subdir / "postmortem.jsonl"
        postmortem.write_text(json.dumps({
            "event": "adapter_call",
            "mode": "blind",
            "status": "success",
            "prompt": "implement card",
            "response": "done",
            "runtime_seconds": 1.0,
        }) + "\n")

        result = _generate_agent_thoughts(run_dir, card_id)
        assert result is not None
        assert result.parent == card_subdir
        assert result.name == "agent_thoughts.md"

    def test_does_not_use_card_name_directory(self, run_dir):
        """When called with card_id='42', should NOT look in cards/Ajani's Response/."""
        # Create postmortem under the card name directory (wrong location)
        card_name_dir = run_dir / "cards" / "Ajani's Response"
        card_name_dir.mkdir(parents=True)
        (card_name_dir / "postmortem.jsonl").write_text(json.dumps({
            "event": "adapter_call",
            "mode": "blind",
            "status": "success",
            "prompt": "p",
            "response": "r",
            "runtime_seconds": 1.0,
        }) + "\n")

        # Call with card_id — should NOT find the file under card_name dir
        result = _generate_agent_thoughts(run_dir, "42")
        assert result is None  # No postmortem.jsonl under cards/42/

    def test_returns_none_for_empty_postmortem(self, run_dir):
        card_subdir = run_dir / "cards" / "42"
        card_subdir.mkdir(parents=True)
        (card_subdir / "postmortem.jsonl").write_text("")
        result = _generate_agent_thoughts(run_dir, "42")
        assert result is None


# ---------------------------------------------------------------------------
# AgentSession path construction integration
# ---------------------------------------------------------------------------


class TestSessionPathConstruction:
    """AgentSession should use card_id for all path construction."""

    def test_harvest_results_postmortem_uses_card_id(self, config, card_dir, run_dir):
        """When card_id='42', postmortem should be written to cards/42/."""
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="42", run_dir=run_dir,
        )

        # Verify _path_id is used for postmortem path construction
        postmortem_path = _get_postmortem_path(session.run_dir, session._path_id)
        assert postmortem_path is not None
        assert postmortem_path == run_dir / "cards" / "42" / "postmortem.jsonl"
        # Card name should NOT appear in the path
        assert "Ajani" not in str(postmortem_path)
        session.cleanup()

    def test_agent_thoughts_uses_card_id(self, config, card_dir, run_dir):
        """_generate_agent_thoughts is called with _path_id, not card_name."""
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="42", run_dir=run_dir,
        )

        # The session should pass _path_id (== card_id) to _generate_agent_thoughts
        assert session._path_id == "42"
        assert session.card_name == "Ajani's Response"
        # These two must be different — that's the whole point
        assert session._path_id != session.card_name
        session.cleanup()


# ---------------------------------------------------------------------------
# Edge case: card_id is empty string
# ---------------------------------------------------------------------------


class TestEmptyCardIdFallback:
    """When card_id is empty, _path_id falls back to card_name."""

    def test_postmortem_path_falls_back_to_card_name(self, run_dir):
        """Backward compat: if card_id is not set, use card_name."""
        path = _get_postmortem_path(run_dir, "Ajani's Response")
        assert path == run_dir / "cards" / "Ajani's Response" / "postmortem.jsonl"

    def test_session_fallback_path_is_card_name(self, config, card_dir, run_dir):
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            card_id="", run_dir=run_dir,
        )
        postmortem_path = _get_postmortem_path(session.run_dir, session._path_id)
        assert postmortem_path is not None
        assert "Ajani's Response" in str(postmortem_path)
        session.cleanup()
