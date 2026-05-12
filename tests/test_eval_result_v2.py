"""Tests for TODO item 9: EvalResult v2 schema.

Tests verify:
- EvalResultV2 dataclass has correct fields and defaults.
- V2 round-trip: save_card_result_v2 → load_card_result produces matching data.
- V1 backward compat: load_card_result normalises v1 format to v2.
- V1 implementation flattening: nested blind/tested → flat dict.
- V2 result.json has correct schema_version and structure.
- Scorer v2 mode-aware scoring: blind → Category 1, impl_test → Category 2.
- CLI and post_eval use v2 writer.
- Missing optional fields: self_eval=None for blind mode, audited_eval=None.
- Edge cases: empty errors, zero counts, missing v1 fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.evaluator import EvalResultV2
from silverquillm.results import (
    load_card_result,
    save_card_result_v2,
)
from silverquillm.scorer import _v2_to_eval_dicts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_v2_result(**overrides) -> EvalResultV2:
    """Create an EvalResultV2 with sensible defaults for testing."""
    defaults = dict(
        card_id="SOS-001",
        mode="impl_test",
        model_name="claude-sonnet-4",
        adapter="aider",
        status="completed",
        complexity_tier="medium",
        implementation={
            "tokens": {"input": 1000, "output": 500, "total": 1500},
            "runtime_ms": 12345,
            "peak_context": 2000,
        },
        self_eval={"passed": 3, "failed": 1, "total": 4},
        audited_eval={"passed": 5, "failed": 0, "total": 5},
        engine_diff_summary="Added new mechanic",
        errors=[],
    )
    defaults.update(overrides)
    return EvalResultV2(**defaults)


def _write_v1_result(card_dir: Path, data: dict) -> None:
    """Write a v1-style result.json into card_dir."""
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "result.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# EvalResultV2 dataclass
# ---------------------------------------------------------------------------


class TestEvalResultV2Dataclass:
    """Verify EvalResultV2 dataclass structure and defaults."""

    def test_required_fields(self):
        """EvalResultV2 requires card_id, mode, model_name, adapter, status, complexity_tier."""
        r = EvalResultV2(
            card_id="SOS-001",
            mode="blind",
            model_name="gpt-4o",
            adapter="opencode",
            status="completed",
            complexity_tier="trivial",
        )
        assert r.card_id == "SOS-001"
        assert r.mode == "blind"
        assert r.model_name == "gpt-4o"
        assert r.adapter == "opencode"
        assert r.status == "completed"
        assert r.complexity_tier == "trivial"

    def test_default_optional_fields(self):
        """Optional fields default to empty/None."""
        r = EvalResultV2(
            card_id="X",
            mode="blind",
            model_name="m",
            adapter="a",
            status="completed",
            complexity_tier="trivial",
        )
        assert r.implementation == {}
        assert r.self_eval is None
        assert r.audited_eval is None
        assert r.engine_diff_summary == ""
        assert r.errors == []

    def test_errors_default_not_shared(self):
        """Each instance gets its own errors list (no mutable default sharing)."""
        r1 = EvalResultV2(card_id="A", mode="blind", model_name="m", adapter="a", status="completed", complexity_tier="t")
        r2 = EvalResultV2(card_id="B", mode="blind", model_name="m", adapter="a", status="completed", complexity_tier="t")
        r1.errors.append("oops")
        assert r2.errors == []


# ---------------------------------------------------------------------------
# V2 round-trip: save → load
# ---------------------------------------------------------------------------


class TestV2RoundTrip:
    """Save EvalResultV2 via save_card_result_v2, load via load_card_result."""

    def test_round_trip_all_fields(self, tmp_path):
        """All v2 fields survive save → load round-trip."""
        result = _make_v2_result()
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")

        assert loaded["schema_version"] == 2
        assert loaded["card_id"] == "SOS-001"
        assert loaded["mode"] == "impl_test"
        assert loaded["model_name"] == "claude-sonnet-4"
        assert loaded["adapter"] == "aider"
        assert loaded["status"] == "completed"
        assert loaded["complexity_tier"] == "medium"
        assert loaded["implementation"]["tokens"]["total"] == 1500
        assert loaded["implementation"]["runtime_ms"] == 12345
        assert loaded["self_eval"] == {"passed": 3, "failed": 1, "total": 4}
        assert loaded["audited_eval"] == {"passed": 5, "failed": 0, "total": 5}
        assert loaded["engine_diff_summary"] == "Added new mechanic"
        assert loaded["errors"] == []

    def test_round_trip_blind_mode_no_self_eval(self, tmp_path):
        """Blind mode with self_eval=None round-trips correctly."""
        result = _make_v2_result(mode="blind", self_eval=None)
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")

        assert loaded["mode"] == "blind"
        assert loaded["self_eval"] is None

    def test_round_trip_no_audited_eval(self, tmp_path):
        """audited_eval=None round-trips correctly."""
        result = _make_v2_result(audited_eval=None)
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")

        assert loaded["audited_eval"] is None

    def test_round_trip_with_errors(self, tmp_path):
        """Errors list persists through round-trip."""
        result = _make_v2_result(errors=["FAILED test_foo", "timeout"])
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")

        assert loaded["errors"] == ["FAILED test_foo", "timeout"]

    def test_round_trip_zero_counts(self, tmp_path):
        """Zero pass/fail counts survive round-trip."""
        result = _make_v2_result(
            self_eval={"passed": 0, "failed": 0, "total": 0},
            audited_eval={"passed": 0, "failed": 0, "total": 0},
        )
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")

        assert loaded["self_eval"]["passed"] == 0
        assert loaded["self_eval"]["total"] == 0
        assert loaded["audited_eval"]["passed"] == 0

    def test_saves_impl_source_file(self, tmp_path):
        """save_card_result_v2 writes card_impl.py when impl_source provided."""
        result = _make_v2_result()
        card_dir = save_card_result_v2(tmp_path, result, impl_source="print('hi')")
        assert (card_dir / "card_impl.py").read_text() == "print('hi')"

    def test_saves_tests_source_file(self, tmp_path):
        """save_card_result_v2 writes tests.py when tests_source provided."""
        result = _make_v2_result()
        card_dir = save_card_result_v2(tmp_path, result, tests_source="def test_x(): pass")
        assert (card_dir / "tests.py").read_text() == "def test_x(): pass"


# ---------------------------------------------------------------------------
# V2 result.json schema
# ---------------------------------------------------------------------------


class TestV2JsonSchema:
    """Verify the saved result.json has correct v2 structure."""

    def test_schema_version_is_2(self, tmp_path):
        """result.json includes schema_version: 2."""
        result = _make_v2_result()
        save_card_result_v2(tmp_path, result)
        raw = json.loads((tmp_path / "cards" / "SOS-001" / "result.json").read_text())
        assert raw["schema_version"] == 2

    def test_all_top_level_keys_present(self, tmp_path):
        """result.json has all expected v2 top-level keys."""
        result = _make_v2_result()
        save_card_result_v2(tmp_path, result)
        raw = json.loads((tmp_path / "cards" / "SOS-001" / "result.json").read_text())

        expected_keys = {
            "schema_version", "card_id", "mode", "model_name", "adapter",
            "status", "complexity_tier", "implementation", "self_eval",
            "audited_eval", "engine_diff_summary", "errors",
        }
        assert expected_keys.issubset(raw.keys())


# ---------------------------------------------------------------------------
# V1 backward compatibility
# ---------------------------------------------------------------------------


class TestV1BackwardCompat:
    """load_card_result normalises v1 format to v2."""

    def test_v1_impl_test_mode_inferred(self, tmp_path):
        """V1 with tested data infers mode='impl_test'."""
        card_dir = tmp_path / "card_a"
        _write_v1_result(card_dir, {
            "card_id": "card_a",
            "model": "gpt-4o",
            "agent": "aider",
            "implementation": {
                "blind": {"source": "..."},
                "tested": {"source": "..."},
            },
            "self_eval": {
                "blind": {"passed": 2, "failed": 1, "total": 3},
                "tested": {"passed": 4, "failed": 0, "total": 4},
            },
        })
        loaded = load_card_result(card_dir)

        assert loaded["schema_version"] == 2
        assert loaded["mode"] == "impl_test"
        assert loaded["model_name"] == "gpt-4o"
        assert loaded["adapter"] == "aider"

    def test_v1_blind_mode_inferred(self, tmp_path):
        """V1 without tested data infers mode='blind'."""
        card_dir = tmp_path / "card_b"
        _write_v1_result(card_dir, {
            "card_id": "card_b",
            "model": "gpt-4o",
            "agent": "opencode",
            "implementation": {
                "blind": {"source": "..."},
            },
            "self_eval": {
                "blind": {"passed": 1, "failed": 2, "total": 3},
            },
        })
        loaded = load_card_result(card_dir)

        assert loaded["mode"] == "blind"

    def test_v1_self_eval_flattened_to_tested(self, tmp_path):
        """V1 nested self_eval is flattened, preferring tested phase."""
        card_dir = tmp_path / "card_c"
        _write_v1_result(card_dir, {
            "card_id": "card_c",
            "model": "m",
            "agent": "a",
            "implementation": {"tested": {"source": "..."}},
            "self_eval": {
                "blind": {"passed": 1, "failed": 0, "total": 1},
                "tested": {"passed": 7, "failed": 2, "total": 9},
            },
        })
        loaded = load_card_result(card_dir)

        assert loaded["self_eval"] == {"passed": 7, "failed": 2, "total": 9}

    def test_v1_audited_eval_flattened(self, tmp_path):
        """V1 nested audited_eval is flattened."""
        card_dir = tmp_path / "card_d"
        _write_v1_result(card_dir, {
            "card_id": "card_d",
            "model": "m",
            "agent": "a",
            "implementation": {"tested": {"source": "..."}},
            "audited_eval": {
                "tested": {"passed": 10, "failed": 1, "total": 11},
            },
        })
        loaded = load_card_result(card_dir)

        assert loaded["audited_eval"] == {"passed": 10, "failed": 1, "total": 11}

    def test_v1_missing_fields_get_defaults(self, tmp_path):
        """V1 with minimal fields gets safe defaults."""
        card_dir = tmp_path / "card_e"
        _write_v1_result(card_dir, {
            "card_id": "card_e",
        })
        loaded = load_card_result(card_dir)

        assert loaded["schema_version"] == 2
        assert loaded["card_id"] == "card_e"
        assert loaded["status"] == "completed"
        assert loaded["complexity_tier"] == "unknown"
        assert loaded["model_name"] == "unknown"
        assert loaded["adapter"] == "unknown"

    def test_v1_no_self_eval_becomes_none(self, tmp_path):
        """V1 without self_eval → self_eval=None in v2."""
        card_dir = tmp_path / "card_f"
        _write_v1_result(card_dir, {
            "card_id": "card_f",
            "model": "m",
            "agent": "a",
            "implementation": {},
        })
        loaded = load_card_result(card_dir)

        assert loaded["self_eval"] is None

    def test_file_not_found_raises(self, tmp_path):
        """load_card_result raises FileNotFoundError for missing result.json."""
        with pytest.raises(FileNotFoundError):
            load_card_result(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# Scorer v2 compatibility
# ---------------------------------------------------------------------------


class TestScorerV2Compat:
    """_v2_to_eval_dicts converts v2 records to scorer-compatible flat dicts."""

    def test_self_eval_produces_flat_dict(self):
        """V2 with self_eval (no mode) produces a flat dict with eval_type='self'."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-010",
            "adapter": "aider",
            "self_eval": {"passed": 3, "failed": 1, "total": 4},
            "audited_eval": None,
        }
        flat = _v2_to_eval_dicts(v2)
        self_dicts = [d for d in flat if d["eval_type"] == "self"]
        assert len(self_dicts) == 1
        assert self_dicts[0]["agent"] == "aider"
        assert self_dicts[0]["card_id"] == "SOS-010"
        # No mode specified → backward compat populates both columns
        assert self_dicts[0]["blind_passed"] == 3
        assert self_dicts[0]["tested_passed"] == 3

    def test_audited_eval_produces_flat_dict(self):
        """V2 with audited_eval (no mode) produces a flat dict with eval_type='audited'."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-020",
            "adapter": "opencode",
            "self_eval": None,
            "audited_eval": {"passed": 5, "failed": 2, "total": 7},
        }
        flat = _v2_to_eval_dicts(v2)
        audited_dicts = [d for d in flat if d["eval_type"] == "audited"]
        assert len(audited_dicts) == 1
        # No mode → both columns populated
        assert audited_dicts[0]["blind_passed"] == 5
        assert audited_dicts[0]["blind_total"] == 7
        assert audited_dicts[0]["tested_passed"] == 5
        assert audited_dicts[0]["tested_total"] == 7

    def test_both_evals_produce_two_dicts(self):
        """V2 with both self_eval and audited_eval produces two flat dicts."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-030",
            "adapter": "pi",
            "self_eval": {"passed": 2, "failed": 0, "total": 2},
            "audited_eval": {"passed": 4, "failed": 1, "total": 5},
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 2
        eval_types = {d["eval_type"] for d in flat}
        assert eval_types == {"self", "audited"}

    def test_no_evals_produces_empty_list(self):
        """V2 with no self_eval or audited_eval produces no flat dicts."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-040",
            "adapter": "aider",
            "self_eval": None,
            "audited_eval": None,
        }
        flat = _v2_to_eval_dicts(v2)
        assert flat == []

    def test_scorer_loads_v2_results_json(self, tmp_path):
        """Scorer _load_eval_results handles v2 records in results.json."""
        from silverquillm.scorer import _load_eval_results

        v2_record = {
            "schema_version": 2,
            "card_id": "SOS-050",
            "adapter": "aider",
            "self_eval": {"passed": 3, "failed": 0, "total": 3},
            "audited_eval": {"passed": 2, "failed": 1, "total": 3},
        }
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        (results_dir / "results.json").write_text(json.dumps([v2_record]))

        loaded = _load_eval_results(results_dir)
        assert len(loaded) == 2  # one self, one audited
        assert all(d["agent"] == "aider" for d in loaded)
        assert all(d["card_id"] == "SOS-050" for d in loaded)


# ---------------------------------------------------------------------------
# Scorer mode-aware scoring (Category 1 vs Category 2)
# ---------------------------------------------------------------------------


class TestScorerModeAware:
    """_v2_to_eval_dicts respects mode: blind → Category 1, impl_test → Category 2."""

    def test_blind_mode_populates_only_blind_columns(self):
        """mode='blind' → self_eval goes into blind_passed/blind_total only (Cat 1)."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-100",
            "mode": "blind",
            "adapter": "aider",
            "self_eval": {"passed": 5, "failed": 2, "total": 7},
            "audited_eval": None,
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 1
        d = flat[0]
        assert d["blind_passed"] == 5
        assert d["blind_total"] == 7
        assert d["tested_passed"] == 0
        assert d["tested_total"] == 0

    def test_impl_test_mode_populates_only_tested_columns(self):
        """mode='impl_test' → self_eval goes into tested_passed/tested_total only (Cat 2)."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-101",
            "mode": "impl_test",
            "adapter": "aider",
            "self_eval": {"passed": 4, "failed": 1, "total": 5},
            "audited_eval": None,
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 1
        d = flat[0]
        assert d["tested_passed"] == 4
        assert d["tested_total"] == 5
        assert d["blind_passed"] == 0
        assert d["blind_total"] == 0

    def test_blind_mode_audited_only_blind_columns(self):
        """mode='blind' → audited_eval goes into blind columns only."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-102",
            "mode": "blind",
            "adapter": "opencode",
            "self_eval": None,
            "audited_eval": {"passed": 8, "failed": 1, "total": 9},
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 1
        d = flat[0]
        assert d["blind_passed"] == 8
        assert d["blind_total"] == 9
        assert d["tested_passed"] == 0
        assert d["tested_total"] == 0

    def test_impl_test_mode_audited_only_tested_columns(self):
        """mode='impl_test' → audited_eval goes into tested columns only."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-103",
            "mode": "impl_test",
            "adapter": "opencode",
            "self_eval": None,
            "audited_eval": {"passed": 6, "failed": 3, "total": 9},
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 1
        d = flat[0]
        assert d["tested_passed"] == 6
        assert d["tested_total"] == 9
        assert d["blind_passed"] == 0
        assert d["blind_total"] == 0

    def test_no_mode_populates_both_columns_backward_compat(self):
        """Missing mode → both blind and tested columns populated (backward compat)."""
        v2 = {
            "schema_version": 2,
            "card_id": "SOS-104",
            "adapter": "aider",
            "self_eval": {"passed": 3, "failed": 0, "total": 3},
            "audited_eval": None,
        }
        flat = _v2_to_eval_dicts(v2)
        assert len(flat) == 1
        d = flat[0]
        assert d["blind_passed"] == 3
        assert d["blind_total"] == 3
        assert d["tested_passed"] == 3
        assert d["tested_total"] == 3


# ---------------------------------------------------------------------------
# V1 normalization: implementation flattening
# ---------------------------------------------------------------------------


class TestV1ImplementationFlattening:
    """load_card_result flattens v1 nested implementation to flat dict."""

    def test_v1_nested_impl_flattened_to_tested(self, tmp_path):
        """V1 with implementation.blind and implementation.tested → flat dict from tested."""
        card_dir = tmp_path / "card_impl_flat"
        _write_v1_result(card_dir, {
            "card_id": "card_impl_flat",
            "model": "gpt-4o",
            "agent": "aider",
            "implementation": {
                "blind": {"source": "blind_code", "tokens": 100},
                "tested": {"source": "tested_code", "tokens": 500},
            },
        })
        loaded = load_card_result(card_dir)

        # Implementation should be flat (from the tested phase), not nested
        impl = loaded["implementation"]
        assert "blind" not in impl
        assert "tested" not in impl
        # Should contain the tested phase's data directly
        assert impl.get("source") == "tested_code"
        assert impl.get("tokens") == 500

    def test_v1_blind_only_impl_flattened(self, tmp_path):
        """V1 with only implementation.blind → flat dict from blind."""
        card_dir = tmp_path / "card_blind_impl"
        _write_v1_result(card_dir, {
            "card_id": "card_blind_impl",
            "model": "gpt-4o",
            "agent": "aider",
            "implementation": {
                "blind": {"source": "blind_code", "tokens": 200},
            },
        })
        loaded = load_card_result(card_dir)

        impl = loaded["implementation"]
        assert "blind" not in impl
        assert impl.get("source") == "blind_code"
        assert impl.get("tokens") == 200

    def test_v1_empty_impl_stays_empty(self, tmp_path):
        """V1 with empty implementation → empty dict."""
        card_dir = tmp_path / "card_empty_impl"
        _write_v1_result(card_dir, {
            "card_id": "card_empty_impl",
            "model": "m",
            "agent": "a",
            "implementation": {},
        })
        loaded = load_card_result(card_dir)

        assert loaded["implementation"] == {}


# ---------------------------------------------------------------------------
# CLI uses v2 writer
# ---------------------------------------------------------------------------


class TestCLIUsesV2Writer:
    """Verify cli.py calls save_card_result_v2 during card processing."""

    def test_cli_imports_save_card_result_v2(self):
        """cli.py imports save_card_result_v2 from results module."""
        from silverquillm import cli
        assert hasattr(cli, "save_card_result_v2"), (
            "cli module should import save_card_result_v2"
        )

    def test_cli_imports_eval_result_v2(self):
        """cli.py imports EvalResultV2 for constructing v2 results."""
        from silverquillm import cli
        assert hasattr(cli, "EvalResultV2"), (
            "cli module should import EvalResultV2"
        )


# ---------------------------------------------------------------------------
# post_eval uses v2 format
# ---------------------------------------------------------------------------


class TestPostEvalV2Format:
    """Verify post_eval writes result.json in v2 schema."""

    def test_merge_result_json_writes_schema_version_2(self, tmp_path):
        """_merge_result_json writes schema_version: 2 to result.json."""
        from silverquillm.post_eval import CardEvalResult, _merge_result_json

        card_dir = tmp_path / "card_pe"
        card_dir.mkdir(parents=True)

        card_result = CardEvalResult(
            card_id="card_pe",
            self_eval_passed=3,
            self_eval_failed=1,
            self_eval_total=4,
        )
        _merge_result_json(card_dir, card_result, mode="impl_test")

        raw = json.loads((card_dir / "result.json").read_text())
        assert raw["schema_version"] == 2
        assert raw["mode"] == "impl_test"

    def test_merge_result_json_writes_self_eval_for_impl_test(self, tmp_path):
        """_merge_result_json writes self_eval block for impl_test mode."""
        from silverquillm.post_eval import CardEvalResult, _merge_result_json

        card_dir = tmp_path / "card_pe2"
        card_dir.mkdir(parents=True)

        card_result = CardEvalResult(
            card_id="card_pe2",
            self_eval_passed=5,
            self_eval_failed=2,
            self_eval_total=7,
        )
        _merge_result_json(card_dir, card_result, mode="impl_test")

        raw = json.loads((card_dir / "result.json").read_text())
        assert raw["self_eval"] == {"passed": 5, "failed": 2, "total": 7}

    def test_merge_result_json_blind_mode_no_self_eval(self, tmp_path):
        """_merge_result_json in blind mode sets self_eval to None when no tests run."""
        from silverquillm.post_eval import CardEvalResult, _merge_result_json

        card_dir = tmp_path / "card_pe3"
        card_dir.mkdir(parents=True)

        card_result = CardEvalResult(card_id="card_pe3")
        _merge_result_json(card_dir, card_result, mode="blind")

        raw = json.loads((card_dir / "result.json").read_text())
        assert raw["mode"] == "blind"
        assert raw["self_eval"] is None

    def test_merge_result_json_writes_audited_eval(self, tmp_path):
        """_merge_result_json writes audited_eval block."""
        from silverquillm.post_eval import CardEvalResult, _merge_result_json

        card_dir = tmp_path / "card_pe4"
        card_dir.mkdir(parents=True)

        card_result = CardEvalResult(
            card_id="card_pe4",
            audited_passed=10,
            audited_failed=1,
            audited_total=11,
        )
        _merge_result_json(card_dir, card_result, mode="impl_test")

        raw = json.loads((card_dir / "result.json").read_text())
        assert raw["audited_eval"] == {"passed": 10, "failed": 1, "total": 11}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for v2 schema handling."""

    def test_status_timeout(self, tmp_path):
        """status='timeout' persists through round-trip."""
        result = _make_v2_result(status="timeout")
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")
        assert loaded["status"] == "timeout"

    def test_status_no_output(self, tmp_path):
        """status='no_output' persists through round-trip."""
        result = _make_v2_result(status="no_output")
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")
        assert loaded["status"] == "no_output"

    def test_empty_implementation_dict(self, tmp_path):
        """Empty implementation dict round-trips."""
        result = _make_v2_result(implementation={})
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")
        assert loaded["implementation"] == {}

    def test_empty_engine_diff_summary(self, tmp_path):
        """Empty engine_diff_summary round-trips."""
        result = _make_v2_result(engine_diff_summary="")
        save_card_result_v2(tmp_path, result)
        loaded = load_card_result(tmp_path / "cards" / "SOS-001")
        assert loaded["engine_diff_summary"] == ""

    def test_v2_passthrough_already_v2(self, tmp_path):
        """load_card_result passes through already-v2 records without modification."""
        card_dir = tmp_path / "card_v2"
        card_dir.mkdir(parents=True)
        v2_data = {
            "schema_version": 2,
            "card_id": "SOS-099",
            "mode": "blind",
            "model_name": "test",
            "adapter": "test",
            "status": "completed",
            "complexity_tier": "simple",
            "implementation": {},
            "self_eval": None,
            "audited_eval": None,
            "engine_diff_summary": "",
            "errors": [],
        }
        (card_dir / "result.json").write_text(json.dumps(v2_data))
        loaded = load_card_result(card_dir)

        assert loaded == v2_data
