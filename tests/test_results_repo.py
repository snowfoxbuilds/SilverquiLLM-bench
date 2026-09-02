"""Tests for ``silverquillm/results_repo.py`` — the private results repo (#39 §3, #63).

Covers the schema (identity, ``RunRecord`` validation), the immutable atomic
writer, the single-owner ``leaderboard_valid`` rule with the real ``"1"`` vs
``"001"`` collector-number shapes, the derived index's determinism, the
``--results-repo`` / ``SILVERQUILLM_RESULTS_REPO`` resolution, and
``silverquillm results-init``.
"""

from __future__ import annotations

import json
import pathlib
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from silverquillm import results_repo as rr
from silverquillm.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SOS_CONFIG = json.loads((REPO_ROOT / "benchmarks" / "sos" / "config.json").read_text())
SMOKE_CONFIG = json.loads((REPO_ROOT / "benchmarks" / "smoke" / "config.json").read_text())

# The real legacy shapes: manifests store unpadded numbers, eval_result keys
# carry the set prefix, config.json zero-pads.
LEGACY_FILTER = ["1", "4", "13", "57", "97", "120", "201", "226", "245", "257"]
SCORED_SOS = [f"sos_{n}" for n in LEGACY_FILTER]


def _scores() -> dict[str, Any]:
    return {
        "card_correctness": {
            "audited_pass_rate": 0.8193,
            "card_pass_rate": 0.3,
            "cards_completed": 10,
            "cards_no_output": 0,
            "cards_timed_out": 0,
        },
        "fdn_regression": {"fdn_test_pass_rate": 1.0, "fdn_card_pass_rate": 0.6364},
        "engine_regression": {"engine_test_pass_rate": 1.0, "engine_churn_lines": 216},
    }


def _record(**overrides: Any) -> rr.RunRecord:
    fields: dict[str, Any] = {
        "run_id": "sos-img-a-2026-06-01T00-00",
        "candidate": rr.CandidateIdentity.legacy("img-a"),
        "mode": "legacy",
        "benchmark": "sos",
        "budget_seconds": 360000,
        "leaderboard_valid": True,
        "resumed_from": None,
        "run_metadata": {"run_date": "2026-06-01T01:00:00Z"},
        "proposal_status": None,
        "scores": _scores(),
        "artifact_pointers": [
            {"kind": rr.LEGACY_TREE_KIND, "location": "docker/img-a/validated_results/run/"}
        ],
    }
    fields.update(overrides)
    return rr.RunRecord(**fields)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestCandidateIdentity:
    def test_legacy_identity_carries_the_image_dir_in_every_hash_field(self) -> None:
        ident = rr.CandidateIdentity.legacy("cc-opus-48-bare")
        assert ident.scheme == rr.LEGACY_SCHEME
        assert ident.base_image_digest == "legacy:cc-opus-48-bare"
        assert ident.instruction_hash == "legacy:cc-opus-48-bare"
        assert ident.adapter_identity == "legacy:cc-opus-48-bare"

    def test_verified_is_false_and_never_defaulted_true(self) -> None:
        assert rr.CandidateIdentity.legacy("x").verified is False
        assert (
            rr.CandidateIdentity.from_dict(
                {
                    "scheme": "legacy",
                    "base_image_digest": "legacy:x",
                    "instruction_hash": "legacy:x",
                    "adapter_identity": "legacy:x",
                }
            ).verified
            is False
        )

    def test_candidate_hash_is_the_sanitized_image_dir(self) -> None:
        assert (
            rr.candidate_hash(rr.CandidateIdentity.legacy("copilot-gpt-5.4")) == "copilot-gpt-5.4"
        )
        assert rr.candidate_hash(rr.CandidateIdentity.legacy("odd name!")) == "odd_name_"

    def test_legacy_image_dir_round_trips(self) -> None:
        assert rr.legacy_image_dir(rr.CandidateIdentity.legacy("img-b")) == "img-b"

    def test_non_legacy_scheme_has_no_hash_rule_yet(self) -> None:
        ident = rr.CandidateIdentity("sha256:abc", "h", "claude", rr.OZOLITH_SCHEME)
        assert rr.legacy_image_dir(ident) is None
        with pytest.raises(rr.ResultsRepoError, match="#65"):
            rr.candidate_hash(ident)

    @pytest.mark.parametrize("bad", ["", ".", "..", "a/b"])
    def test_legacy_rejects_unsafe_image_dirs(self, bad: str) -> None:
        with pytest.raises(rr.InvalidRunRecordError):
            rr.CandidateIdentity.legacy(bad)

    def test_dict_round_trip(self) -> None:
        ident = rr.CandidateIdentity.legacy("img-c")
        assert rr.CandidateIdentity.from_dict(ident.to_dict()) == ident


# ---------------------------------------------------------------------------
# RunRecord validation
# ---------------------------------------------------------------------------


class TestRunRecordValidation:
    def test_well_formed_record_validates(self) -> None:
        _record().validate()

    def test_scores_must_have_exactly_the_neutral_keys(self) -> None:
        missing = _scores()
        del missing["engine_regression"]
        with pytest.raises(rr.InvalidRunRecordError, match="exactly the keys"):
            _record(scores=missing).validate()
        sos_specific = {**_scores(), "sos_card_correctness": {}}
        with pytest.raises(rr.InvalidRunRecordError, match="exactly the keys"):
            _record(scores=sos_specific).validate()

    def test_workload_is_rejected_as_retired_vocabulary(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="retired"):
            _record(run_metadata={"workload": "sos-subset"}).validate()

    @pytest.mark.parametrize("bad", ["", ".", "..", ".hidden", "a/b", "a b"])
    def test_run_id_must_be_one_safe_path_segment(self, bad: str) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="run_id"):
            _record(run_id=bad).validate()

    def test_pointer_needs_kind_and_location(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="location"):
            _record(artifact_pointers=[{"kind": "legacy-tree"}]).validate()

    def test_budget_must_be_a_real_int(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError):
            _record(budget_seconds=True).validate()
        with pytest.raises(rr.InvalidRunRecordError):
            _record(budget_seconds=-1).validate()


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


class TestWriteRunRecord:
    def test_layout_and_manifest_shape(self, tmp_path: Path) -> None:
        record = _record()
        run_dir = rr.write_run_record(tmp_path, record)

        assert run_dir == tmp_path / "results" / "img-a" / record.run_id
        manifest = json.loads((run_dir / "manifest.json").read_text())
        scores = json.loads((run_dir / "scores.json").read_text())

        assert manifest["schema_version"] == 1
        assert manifest["benchmark"] == "sos"
        assert "workload" not in manifest
        assert manifest["leaderboard_valid"] is True
        assert manifest["candidate"]["verified"] is False
        assert manifest["candidate_hash"] == run_dir.parent.name
        assert manifest["mode"] == "legacy"
        assert manifest["proposal_status"] is None
        assert manifest["artifact_pointers"] == record.artifact_pointers
        assert set(scores) == set(rr.SCORE_DIMENSIONS)
        assert scores["card_correctness"] == _scores()["card_correctness"]

    def test_refuses_overwrite_and_keeps_the_original(self, tmp_path: Path) -> None:
        first = _record()
        run_dir = rr.write_run_record(tmp_path, first)
        before = (run_dir / "scores.json").read_bytes()

        second = _record(scores={**_scores(), "engine_regression": {"engine_test_pass_rate": 0.0}})
        with pytest.raises(rr.RunRecordExistsError):
            rr.write_run_record(tmp_path, second)

        assert (run_dir / "scores.json").read_bytes() == before
        assert [p.name for p in run_dir.parent.iterdir()] == [first.run_id]  # no temp litter

    def test_serialization_failure_leaves_nothing_behind(self, tmp_path: Path) -> None:
        bad = _record(scores={**_scores(), "engine_regression": {"unserializable": {1, 2}}})
        with pytest.raises(TypeError):
            rr.write_run_record(tmp_path, bad)
        assert not (tmp_path / "results").exists()

    def test_lost_rename_race_is_reported_as_exists_and_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(self: Path, target: Any) -> Path:
            raise OSError("Directory not empty")

        monkeypatch.setattr(pathlib.Path, "rename", _boom)
        with pytest.raises(rr.RunRecordExistsError):
            rr.write_run_record(tmp_path, _record())
        candidate_dir = tmp_path / "results" / "img-a"
        assert list(candidate_dir.iterdir()) == []

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        a = rr.write_run_record(tmp_path / "one", _record())
        b = rr.write_run_record(tmp_path / "two", _record())
        for name in ("manifest.json", "scores.json"):
            assert (a / name).read_bytes() == (b / name).read_bytes()

    def test_read_round_trip(self, tmp_path: Path) -> None:
        record = _record(resumed_from="prior-run", leaderboard_valid=False)
        run_dir = rr.write_run_record(tmp_path, record)
        assert rr.read_run_record(run_dir) == record

    def test_smoke_record_has_the_same_shape_as_a_migrated_sos_record(self, tmp_path: Path) -> None:
        """The #64 driver writes ``benchmark: "smoke"`` records with the same writer."""
        smoke = _record(
            run_id="smoke-vanilla-claude-2026-09-02T10-00",
            candidate=rr.CandidateIdentity.legacy("vanilla-claude"),
            mode="basic",
            benchmark="smoke",
            leaderboard_valid=False,
            proposal_status="applied",
            artifact_pointers=[],
        )
        sos_dir = rr.write_run_record(tmp_path, _record())
        smoke_dir = rr.write_run_record(tmp_path, smoke)
        sos_scores = json.loads((sos_dir / "scores.json").read_text())
        smoke_scores = json.loads((smoke_dir / "scores.json").read_text())
        assert set(sos_scores) == set(smoke_scores) == set(rr.SCORE_DIMENSIONS)
        manifest = json.loads((smoke_dir / "manifest.json").read_text())
        assert manifest["benchmark"] == "smoke"
        assert manifest["proposal_status"] == "applied"
        assert manifest["leaderboard_valid"] is False

    def test_read_rejects_a_manifest_carrying_workload(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["workload"] = "sos"
        manifest_path.write_text(json.dumps(manifest))
        with pytest.raises(rr.InvalidRunRecordError, match="workload"):
            rr.read_run_record(run_dir)


# ---------------------------------------------------------------------------
# leaderboard_valid
# ---------------------------------------------------------------------------


class TestDeriveLeaderboardValid:
    def test_unpadded_legacy_filter_equals_the_padded_config_set(self) -> None:
        assert rr.derive_leaderboard_valid(SOS_CONFIG, LEGACY_FILTER, None, SCORED_SOS) is True

    def test_padded_filter_and_bare_scored_numbers_are_the_same_cards(self) -> None:
        assert (
            rr.derive_leaderboard_valid(SOS_CONFIG, SOS_CONFIG["cards"], None, LEGACY_FILTER)
            is True
        )

    def test_no_filter_with_the_full_scored_set_is_valid(self) -> None:
        assert rr.derive_leaderboard_valid(SOS_CONFIG, None, None, SCORED_SOS) is True

    def test_narrower_filter_is_invalid(self) -> None:
        reasons = rr.leaderboard_validity_reasons(
            SOS_CONFIG, LEGACY_FILTER[:3], None, SCORED_SOS[:3]
        )
        assert any("card filter" in r for r in reasons)
        assert (
            rr.derive_leaderboard_valid(SOS_CONFIG, LEGACY_FILTER[:3], None, SCORED_SOS[:3])
            is False
        )

    def test_resume_leg_is_invalid(self) -> None:
        reasons = rr.leaderboard_validity_reasons(
            SOS_CONFIG, LEGACY_FILTER, "prior-leg", SCORED_SOS
        )
        assert reasons == ["Resume Leg (resumed_from=prior-leg)"]

    def test_ineligible_benchmark_is_invalid_even_when_sets_match(self) -> None:
        assert SMOKE_CONFIG["leaderboard"]["eligible"] is False
        scored = [f"fdn_{n}" for n in SMOKE_CONFIG["cards"]]
        reasons = rr.leaderboard_validity_reasons(SMOKE_CONFIG, SMOKE_CONFIG["cards"], None, scored)
        assert reasons == ["benchmark is not leaderboard-eligible (leaderboard.eligible: false)"]

    def test_eligible_defaults_to_true_when_absent(self) -> None:
        assert "eligible" not in SOS_CONFIG["leaderboard"]
        assert rr.derive_leaderboard_valid(SOS_CONFIG, None, None, SCORED_SOS) is True

    def test_pre_audited_set_271_card_run_is_invalid(self) -> None:
        scored = [f"sos_{n}" for n in range(1, 272)]
        reasons = rr.leaderboard_validity_reasons(SOS_CONFIG, None, None, scored)
        assert reasons == ["scored card set (271 cards) differs from the benchmark's 10-card set"]

    def test_empty_pool_never_validates(self) -> None:
        config = {"cards": [], "leaderboard": {}}
        assert rr.derive_leaderboard_valid(config, None, None, ["sos_1"]) is False

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("001", "1"),
            ("1", "1"),
            ("sos_001", "1"),
            ("sos_1", "1"),
            (7, "7"),
            ("fdn_129", "129"),
            ("12a", "12a"),
            (" 004 ", "4"),
        ],
    )
    def test_normalize_collector_number(self, raw: str | int, expected: str) -> None:
        assert rr.normalize_collector_number(raw) == expected


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestResolveResultsRepo:
    def test_flag_wins_over_env(self) -> None:
        env = {rr.RESULTS_REPO_ENV: "/from/env"}
        assert rr.resolve_results_repo("/from/flag", env) == Path("/from/flag")

    def test_env_used_when_flag_absent(self) -> None:
        assert rr.resolve_results_repo(None, {rr.RESULTS_REPO_ENV: "/from/env"}) == Path(
            "/from/env"
        )

    def test_absent_means_feature_off(self) -> None:
        assert rr.resolve_results_repo(None, {}) is None
        assert rr.resolve_results_repo(None, {rr.RESULTS_REPO_ENV: "  "}) is None

    def test_reads_the_process_environment_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(rr.RESULTS_REPO_ENV, "/proc/env")
        assert rr.resolve_results_repo(None) == Path("/proc/env")
        monkeypatch.delenv(rr.RESULTS_REPO_ENV)
        assert rr.resolve_results_repo(None) is None


class TestLoadBenchmarkConfig:
    def test_loads_the_real_sos_config(self) -> None:
        assert rr.load_benchmark_config(REPO_ROOT, "sos")["id"] == "sos"

    def test_missing_benchmark_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(rr.ResultsRepoError, match="no benchmark config"):
            rr.load_benchmark_config(tmp_path, "nope")

    def test_unsafe_id_is_rejected(self) -> None:
        with pytest.raises(rr.ResultsRepoError, match="invalid benchmark id"):
            rr.load_benchmark_config(REPO_ROOT, "../sos")


# ---------------------------------------------------------------------------
# Derived index
# ---------------------------------------------------------------------------


class TestRebuildIndex:
    def _populate(self, repo: Path) -> None:
        # Written out of order on purpose: the index must not depend on it.
        rr.write_run_record(
            repo, _record(run_id="run-b", candidate=rr.CandidateIdentity.legacy("img-z"))
        )
        rr.write_run_record(repo, _record(run_id="run-c"))
        rr.write_run_record(
            repo,
            _record(
                run_id="run-a",
                leaderboard_valid=False,
                run_metadata={"run_date": "2026-05-01T00:00:00Z"},
            ),
        )

    def test_rows_are_sorted_and_carry_the_documented_fields(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        rows = rr.rebuild_index(tmp_path)
        assert [(r["candidate_hash"], r["run_id"]) for r in rows] == [
            ("img-a", "run-a"),
            ("img-a", "run-c"),
            ("img-z", "run-b"),
        ]
        assert set(rows[0]) == {
            "candidate_hash",
            "run_id",
            "benchmark",
            "mode",
            "leaderboard_valid",
            "run_date",
        }
        assert rows[0]["leaderboard_valid"] is False
        assert rows[0]["run_date"] == "2026-05-01T00:00:00Z"

    def test_two_rebuilds_are_byte_identical(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        rr.rebuild_index(tmp_path)
        first = (tmp_path / "runs.jsonl").read_bytes()
        rr.rebuild_index(tmp_path)
        assert (tmp_path / "runs.jsonl").read_bytes() == first
        assert first.count(b"\n") == 3

    def test_hand_edits_are_overwritten_from_the_tree(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        (tmp_path / "runs.jsonl").write_text('{"run_id": "hand-edited"}\n')
        rr.rebuild_index(tmp_path)
        assert "hand-edited" not in (tmp_path / "runs.jsonl").read_text()

    def test_in_flight_temp_dirs_and_manifestless_dirs_are_ignored(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        stray = tmp_path / "results" / "img-a" / ".tmp-run-d-xyz"
        stray.mkdir()
        (stray / "manifest.json").write_text("{}")
        (tmp_path / "results" / "img-a" / "no-manifest-here").mkdir()
        assert [p.name for p in rr.iter_run_dirs(tmp_path)] == ["run-a", "run-c", "run-b"]

    def test_empty_repo_yields_an_empty_index(self, tmp_path: Path) -> None:
        assert rr.rebuild_index(tmp_path) == []
        assert (tmp_path / "runs.jsonl").read_bytes() == b""


# ---------------------------------------------------------------------------
# results-init
# ---------------------------------------------------------------------------


class TestResultsInit:
    def test_cli_lays_out_an_empty_repo(self, tmp_path: Path) -> None:
        target = tmp_path / "results-clone"
        result = CliRunner().invoke(cli_main, ["results-init", str(target)])
        assert result.exit_code == 0, result.output
        assert (target / "AGENTS.md").is_file()
        assert (target / "results" / ".gitkeep").is_file()
        assert (target / "runs.jsonl").read_bytes() == b""
        assert result.output.count("wrote ") == 3

    def test_cli_refuses_a_non_empty_repo(self, tmp_path: Path) -> None:
        rr.init_results_repo(tmp_path)
        result = CliRunner().invoke(cli_main, ["results-init", str(tmp_path)])
        assert result.exit_code != 0
        assert "AGENTS.md exists" in result.output

    def test_agents_md_documents_the_schema(self, tmp_path: Path) -> None:
        rr.init_results_repo(tmp_path)
        text = (tmp_path / "AGENTS.md").read_text()
        for needle in (
            "results/<candidate-hash>/<run-id>/manifest.json",
            "scores.json",
            "Records are immutable",
            "Index is derived",
            "leaderboard_valid",
            "`benchmark`, never `workload`",
            "self-contained",
            "card_correctness",
            "legacy-tree",
            "proposal_status",
        ):
            assert needle in text, needle

    def test_template_is_packaged(self) -> None:
        assert (rr.TEMPLATE_DIR / "AGENTS.md").is_file()
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert "results_repo_templates" in pyproject
