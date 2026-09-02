"""Tests for ``scripts/migrate_validated_results.py`` — the legacy backfill (#63 Part B).

Fixture trees exercise every legacy manifest shape the corpus survey found
(``card_filter`` unpadded, the older ``cards`` key, a missing
``benchmark_set``, a Resume Leg, a null-filter 271-card run, a
``workspace_final``-only run), plus dry-run / idempotency / source-tree
invariance.  A final class pins the known facts of the real corpus under
``docker/*/validated_results/`` so the migrator's plan is checked against the
data it will actually run on.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from silverquillm import results_repo as rr

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "migrate_validated_results.py"

_spec = importlib.util.spec_from_file_location("migrate_validated_results", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["migrate_validated_results"] = _mod
_spec.loader.exec_module(_mod)

SOS_CONFIG_TEXT = (REPO_ROOT / "benchmarks" / "sos" / "config.json").read_text()
LEGACY_FILTER = ["1", "4", "13", "57", "97", "120", "201", "226", "245", "257"]
SOS_10 = [f"sos_{n}" for n in LEGACY_FILTER]

KNOWN_SKIPPED = {
    "sos-cc-fable-5-bare-xhigh-planned-2026-06-09T22-22",
    "sos-cc-fable-5-bare-xhigh-planned-2026-06-09T23-42",
    "sos-cc-fable-5-bare-xhigh-planned-2026-06-10T07-08-e3ed",
}
KNOWN_INVALID = {
    "sos-copilot-claude-opus-4.6-2026-05-26T17-17",
    "sos-copilot-gpt-5.4-2026-05-25T04-52",
}


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _summary_blocks() -> dict[str, Any]:
    return {
        "sos_card_correctness": {
            "audited_pass_rate": 0.5,
            "card_pass_rate": 0.2,
            "cards_completed": 10,
            "cards_no_output": 0,
            "cards_timed_out": 0,
        },
        "fdn_regression": {"fdn_test_pass_rate": 1.0, "fdn_card_pass_rate": 0.9},
        "engine_regression": {"engine_test_pass_rate": 1.0, "engine_churn_lines": 12},
    }


def write_legacy_run(
    repo_root: Path,
    image: str,
    run: str,
    *,
    manifest: dict[str, Any] | None = None,
    scored: list[str] | None = None,
    resumed_from: str | None = None,
    summary_extra: dict[str, Any] | None = None,
    workspace_final_only: bool = False,
    summary_card_filter: Any = "unset",
) -> Path:
    """Write one ``docker/<image>/validated_results/<run>/`` fixture run."""
    run_dir = repo_root / "docker" / image / "validated_results" / run
    run_dir.mkdir(parents=True, exist_ok=True)
    if workspace_final_only:
        (run_dir / "workspace_final").mkdir()
        return run_dir

    if manifest is None:
        manifest = {
            "timeout_seconds": 360000,
            "deadline_utc": "2026-06-15T13:35:05Z",
            "docker_image": f"silverquillm-{image}:latest",
            "card_filter": list(LEGACY_FILTER),
            "benchmark_set": "sos",
        }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))

    scored = SOS_10 if scored is None else scored
    summary: dict[str, Any] = {
        "docker_image": manifest.get("docker_image", ""),
        "run_metadata": {
            "image": manifest.get("docker_image", ""),
            "timestamp": "2026-06-11T10:12:45Z",
            "card_count": len(scored),
            "timeout_seconds": 7200,
            "harness_version": "deadbeef",
        },
        **_summary_blocks(),
        "per_card": [],
        "run_status": "completed",
        "wall_clock_seconds": 2186.5,
    }
    if summary_card_filter == "unset":
        summary["card_filter"] = manifest.get("card_filter", manifest.get("cards"))
    else:
        summary["card_filter"] = summary_card_filter
    if resumed_from is not None:
        summary["resumed_from"] = resumed_from
        summary["resumed_image_changed"] = False
    if summary_extra:
        summary.update(summary_extra)
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))

    eval_result = {
        "sos_results": {
            c: {"tests_passed": 1, "tests_failed": 0, "tests_total": 1} for c in scored
        },
        "fdn_results": {},
        "engine_result": {"tests_passed": 5, "tests_failed": 0, "tests_total": 5},
    }
    (run_dir / "eval_result.json").write_text(json.dumps(eval_result, indent=2))

    for card in scored[:2]:
        card_dir = run_dir / "cards" / card
        card_dir.mkdir(parents=True)
        (card_dir / "result.json").write_text(
            json.dumps(
                {
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "tests_total": 1,
                    "tests_hash": "h",
                    "test_nodes": [{"test_node": "tests.py::test_x", "outcome": "pass"}],
                }
            )
        )
    return run_dir


@pytest.fixture
def bench_root(tmp_path: Path) -> Path:
    """A tmp bench repo with the real SOS config and no runs yet."""
    config_dir = tmp_path / "bench" / "benchmarks" / "sos"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(SOS_CONFIG_TEXT)
    return tmp_path / "bench"


@pytest.fixture
def results_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "results-clone"
    rr.init_results_repo(repo)
    return repo


def _loader(bench_root: Path):
    return _mod._config_loader_for(bench_root)


def _legacy(bench_root: Path, image: str, run: str) -> Any:
    run_dir = bench_root / "docker" / image / "validated_results" / run
    return _mod.LegacyRun(image=image, run=run, run_dir=run_dir)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscoverLegacyRuns:
    def test_sorted_by_image_then_run_and_ignores_results_working_dirs(
        self, bench_root: Path
    ) -> None:
        write_legacy_run(bench_root, "img-b", "run-1")
        write_legacy_run(bench_root, "img-a", "run-2")
        write_legacy_run(bench_root, "img-a", "run-1")
        (bench_root / "docker" / "img-a" / "results" / "run-9").mkdir(parents=True)
        runs = _mod.discover_legacy_runs(bench_root)
        assert [(r.image, r.run) for r in runs] == [
            ("img-a", "run-1"),
            ("img-a", "run-2"),
            ("img-b", "run-1"),
        ]
        assert runs[0].location == "docker/img-a/validated_results/run-1/"

    def test_no_docker_dir(self, tmp_path: Path) -> None:
        assert _mod.discover_legacy_runs(tmp_path) == []


# ---------------------------------------------------------------------------
# Record builder — one test per legacy shape
# ---------------------------------------------------------------------------


class TestBuildLegacyRecord:
    def test_standard_run_maps_faithfully(self, bench_root: Path) -> None:
        write_legacy_run(bench_root, "cc-opus-48-bare", "sos-cc-opus-48-bare-2026-05-30T04-02")
        record = _mod.build_legacy_record(
            _legacy(bench_root, "cc-opus-48-bare", "sos-cc-opus-48-bare-2026-05-30T04-02"),
            config_loader=_loader(bench_root),
        )
        record.validate()
        assert record.candidate == rr.CandidateIdentity.legacy("cc-opus-48-bare")
        assert rr.candidate_hash(record.candidate) == "cc-opus-48-bare"
        assert record.mode == "legacy"
        assert record.benchmark == "sos"
        assert record.budget_seconds == 360000
        assert record.leaderboard_valid is True
        assert record.resumed_from is None
        assert record.proposal_status is None
        assert set(record.scores) == set(rr.SCORE_DIMENSIONS)
        assert record.scores["card_correctness"] == _summary_blocks()["sos_card_correctness"]
        assert record.scores["engine_regression"] == _summary_blocks()["engine_regression"]
        assert record.artifact_pointers == [
            {
                "kind": "legacy-tree",
                "location": (
                    "docker/cc-opus-48-bare/validated_results/"
                    "sos-cc-opus-48-bare-2026-05-30T04-02/"
                ),
            }
        ]
        meta = record.run_metadata
        assert meta["image_dir"] == "cc-opus-48-bare"
        assert meta["docker_image"] == "silverquillm-cc-opus-48-bare:latest"
        assert meta["run_date"] == "2026-06-11T10:12:45Z"
        assert meta["card_filter"] == LEGACY_FILTER
        assert meta["scored_card_count"] == 10
        assert meta["budget_seconds_source"] == "run_manifest"
        assert meta["migrated_from"] == record.artifact_pointers[0]["location"]
        assert "validity_note" not in meta
        assert "workload" not in json.dumps(record.manifest_dict())

    def test_older_cards_key_manifest_without_timeout(self, bench_root: Path) -> None:
        write_legacy_run(
            bench_root,
            "cc-sonnet-single",
            "run-cards-key",
            manifest={"benchmark_set": "sos", "cards": list(LEGACY_FILTER)},
        )
        record = _mod.build_legacy_record(
            _legacy(bench_root, "cc-sonnet-single", "run-cards-key"),
            config_loader=_loader(bench_root),
        )
        assert record.leaderboard_valid is True
        assert record.run_metadata["card_filter"] == LEGACY_FILTER
        assert record.budget_seconds == 7200
        assert record.run_metadata["budget_seconds_source"] == "run_summary"
        assert record.run_metadata["docker_image"] == ""

    def test_missing_benchmark_set_falls_back_to_sos(self, bench_root: Path) -> None:
        write_legacy_run(
            bench_root,
            "copilot-gpt-5.4",
            "run-no-bset",
            manifest={"timeout_seconds": 360000, "deadline_utc": "2026-05-29T08:52:47Z"},
            summary_card_filter=None,
        )
        record = _mod.build_legacy_record(
            _legacy(bench_root, "copilot-gpt-5.4", "run-no-bset"), config_loader=_loader(bench_root)
        )
        assert record.benchmark == "sos"
        assert record.run_metadata["card_filter"] is None
        assert record.leaderboard_valid is True  # scored the audited 10 with no filter

    def test_resume_leg_is_invalid_with_a_note(self, bench_root: Path) -> None:
        write_legacy_run(
            bench_root,
            "img",
            "leg-2",
            manifest={
                "timeout_seconds": 100,
                "docker_image": "x",
                "card_filter": list(LEGACY_FILTER),
                "benchmark_set": "sos",
                "resumed_from": "leg-1",
            },
            resumed_from="leg-1",
        )
        record = _mod.build_legacy_record(
            _legacy(bench_root, "img", "leg-2"), config_loader=_loader(bench_root)
        )
        assert record.resumed_from == "leg-1"
        assert record.leaderboard_valid is False
        assert "Resume Leg" in record.run_metadata["validity_note"]
        assert record.run_metadata["resumed_image_changed"] is False

    def test_null_filter_271_card_run_is_invalid_with_a_note(self, bench_root: Path) -> None:
        scored = [f"sos_{n}" for n in range(1, 272)]
        write_legacy_run(
            bench_root,
            "img",
            "full-set",
            manifest={
                "timeout_seconds": 360000,
                "docker_image": "x",
                "card_filter": None,
                "benchmark_set": "sos",
            },
            scored=scored,
        )
        record = _mod.build_legacy_record(
            _legacy(bench_root, "img", "full-set"), config_loader=_loader(bench_root)
        )
        assert record.leaderboard_valid is False
        assert record.run_metadata["validity_note"] == (
            "scored card set (271 cards) differs from the benchmark's 10-card set"
        )
        assert record.run_metadata["scored_card_count"] == 271

    def test_narrower_filter_is_invalid(self, bench_root: Path) -> None:
        write_legacy_run(
            bench_root,
            "img",
            "subset",
            manifest={
                "timeout_seconds": 1,
                "docker_image": "x",
                "card_filter": ["1", "4"],
                "benchmark_set": "sos",
            },
            scored=["sos_1", "sos_4"],
        )
        record = _mod.build_legacy_record(
            _legacy(bench_root, "img", "subset"), config_loader=_loader(bench_root)
        )
        assert record.leaderboard_valid is False
        assert "card filter (2 cards)" in record.run_metadata["validity_note"]

    def test_workspace_final_only_is_unparseable(self, bench_root: Path) -> None:
        write_legacy_run(bench_root, "img", "crashed", workspace_final_only=True)
        expected = "missing run_manifest.json, run_summary.json, eval_result.json"
        with pytest.raises(_mod.LegacyRunUnparseable, match=re.escape(expected)):
            _mod.build_legacy_record(
                _legacy(bench_root, "img", "crashed"), config_loader=_loader(bench_root)
            )

    def test_unknown_benchmark_is_unparseable_not_guessed(self, bench_root: Path) -> None:
        write_legacy_run(
            bench_root,
            "img",
            "odd",
            manifest={
                "timeout_seconds": 1,
                "docker_image": "x",
                "card_filter": None,
                "benchmark_set": "nope",
            },
        )
        with pytest.raises(_mod.LegacyRunUnparseable, match="no benchmark config"):
            _mod.build_legacy_record(
                _legacy(bench_root, "img", "odd"), config_loader=_loader(bench_root)
            )

    def test_missing_summary_block_is_unparseable(self, bench_root: Path) -> None:
        run_dir = write_legacy_run(bench_root, "img", "no-block")
        summary = json.loads((run_dir / "run_summary.json").read_text())
        del summary["fdn_regression"]
        (run_dir / "run_summary.json").write_text(json.dumps(summary))
        with pytest.raises(_mod.LegacyRunUnparseable, match="fdn_regression"):
            _mod.build_legacy_record(
                _legacy(bench_root, "img", "no-block"), config_loader=_loader(bench_root)
            )


# ---------------------------------------------------------------------------
# Plan / apply / CLI
# ---------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _mixed_corpus(bench_root: Path) -> None:
    write_legacy_run(bench_root, "img-a", "run-ok-1")
    write_legacy_run(bench_root, "img-a", "run-ok-2")
    write_legacy_run(
        bench_root,
        "img-b",
        "run-resumed",
        resumed_from="run-ok-1",
        manifest={
            "timeout_seconds": 5,
            "docker_image": "x",
            "card_filter": list(LEGACY_FILTER),
            "benchmark_set": "sos",
            "resumed_from": "run-ok-1",
        },
    )
    write_legacy_run(bench_root, "img-b", "run-crashed", workspace_final_only=True)


class TestPlanAndApply:
    def test_plan_separates_records_from_skips(self, bench_root: Path, results_repo: Path) -> None:
        _mixed_corpus(bench_root)
        plan = _mod.plan_migration(bench_root, results_repo)
        assert [p.record.run_id for p in plan.planned] == ["run-ok-1", "run-ok-2", "run-resumed"]
        assert [(s.legacy.run, s.reason.split(" (")[0]) for s in plan.skipped] == [
            ("run-crashed", "missing run_manifest.json, run_summary.json, eval_result.json"),
        ]
        assert all(not p.already_present for p in plan.planned)
        assert [p.record.leaderboard_valid for p in plan.planned] == [True, True, False]

    def test_dry_run_writes_nothing(
        self, bench_root: Path, results_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _mixed_corpus(bench_root)
        before = _snapshot(results_repo)
        code = _mod.main(["--results-repo", str(results_repo), "--dry-run"], repo_root=bench_root)
        assert code == 0
        assert _snapshot(results_repo) == before
        out, err = capsys.readouterr()
        assert "Planned 3 record(s): 3 to write" in out
        assert "SKIPPED — 1 unparseable run(s)" in out
        assert "run-crashed" in out
        assert "Dry run: nothing written." in out
        assert "1 unparseable run(s) skipped" in err

    def test_apply_writes_records_and_index_then_is_idempotent(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        _mixed_corpus(bench_root)
        source_before = _snapshot(bench_root)

        code = _mod.main(["--results-repo", str(results_repo)], repo_root=bench_root)
        assert code == 0
        first = _snapshot(results_repo)
        assert sorted(p for p in first if p.endswith("manifest.json")) == [
            "results/img-a/run-ok-1/manifest.json",
            "results/img-a/run-ok-2/manifest.json",
            "results/img-b/run-resumed/manifest.json",
        ]
        index_rows = [
            json.loads(line) for line in (results_repo / "runs.jsonl").read_text().splitlines()
        ]
        assert [r["run_id"] for r in index_rows] == ["run-ok-1", "run-ok-2", "run-resumed"]
        assert [r["leaderboard_valid"] for r in index_rows] == [True, True, False]

        plan = _mod.plan_migration(bench_root, results_repo)
        assert all(p.already_present for p in plan.planned)
        assert _mod.apply_migration(plan, results_repo) == []
        assert _snapshot(results_repo) == first  # byte-identical after the re-run

        assert _snapshot(bench_root) == source_before  # source tree never modified

    def test_missing_results_repo_is_a_usage_error(
        self, bench_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(rr.RESULTS_REPO_ENV, raising=False)
        assert _mod.main([], repo_root=bench_root) == 2
        assert rr.RESULTS_REPO_ENV in capsys.readouterr().err

    def test_env_var_selects_the_results_repo(
        self, bench_root: Path, results_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        monkeypatch.setenv(rr.RESULTS_REPO_ENV, str(results_repo))
        assert _mod.main([], repo_root=bench_root) == 0
        assert (results_repo / "results" / "img-a" / "run-ok-1" / "scores.json").is_file()

    def test_format_plan_marks_invalid_runs_with_their_note(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        _mixed_corpus(bench_root)
        text = _mod.format_plan(_mod.plan_migration(bench_root, results_repo), dry_run=True)
        assert (
            "img-b/run-resumed: benchmark=sos mode=legacy leaderboard=INVALID — Resume Leg" in text
        )
        assert "img-a/run-ok-1: benchmark=sos mode=legacy leaderboard=valid" in text


# ---------------------------------------------------------------------------
# Rerun conflicts — a destination is skipped only when byte-identical
# ---------------------------------------------------------------------------


class TestMigrationConflicts:
    def test_exact_existing_record_is_skipped_not_conflicting(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        _mod.apply_migration(_mod.plan_migration(bench_root, results_repo), results_repo)
        again = _mod.plan_migration(bench_root, results_repo)
        assert again.conflicts == []
        assert [p.already_present for p in again.planned] == [True]
        assert _mod.apply_migration(again, results_repo) == []

    def test_empty_existing_directory_is_a_conflict(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        (results_repo / "results" / "img-a" / "run-ok-1").mkdir(parents=True)
        plan = _mod.plan_migration(bench_root, results_repo)
        assert plan.planned == []
        assert [c.legacy.run for c in plan.conflicts] == ["run-ok-1"]
        assert "unreadable" in plan.conflicts[0].reason
        with pytest.raises(rr.ResultsRepoError, match="conflict"):
            _mod.apply_migration(plan, results_repo)

    def test_malformed_existing_manifest_is_a_conflict(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        _mod.apply_migration(_mod.plan_migration(bench_root, results_repo), results_repo)
        manifest = results_repo / "results" / "img-a" / "run-ok-1" / "manifest.json"
        manifest.write_text("{not json")
        plan = _mod.plan_migration(bench_root, results_repo)
        assert [c.legacy.run for c in plan.conflicts] == ["run-ok-1"]
        assert "unreadable" in plan.conflicts[0].reason

    def test_incomplete_existing_record_is_a_conflict(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        _mod.apply_migration(_mod.plan_migration(bench_root, results_repo), results_repo)
        (results_repo / "results" / "img-a" / "run-ok-1" / "scores.json").unlink()
        plan = _mod.plan_migration(bench_root, results_repo)
        assert [c.legacy.run for c in plan.conflicts] == ["run-ok-1"]
        assert "unreadable" in plan.conflicts[0].reason

    def test_differing_valid_existing_record_is_a_conflict(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        record = _mod.plan_migration(bench_root, results_repo).planned[0].record
        altered = dataclasses.replace(record, budget_seconds=record.budget_seconds + 1)
        rr.write_run_record(results_repo, altered)
        before = _snapshot(results_repo)
        plan = _mod.plan_migration(bench_root, results_repo)
        assert [c.reason for c in plan.conflicts] == [
            "existing record differs from the record this run would write"
        ]
        with pytest.raises(rr.ResultsRepoError, match="conflict"):
            _mod.apply_migration(plan, results_repo)
        assert _snapshot(results_repo) == before  # the differing record is never touched

    def test_conflicts_block_the_missing_records_too(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        write_legacy_run(bench_root, "img-a", "run-ok-2")
        (results_repo / "results" / "img-a" / "run-ok-1").mkdir(parents=True)
        plan = _mod.plan_migration(bench_root, results_repo)
        assert [p.record.run_id for p in plan.planned] == ["run-ok-2"]
        assert [c.legacy.run for c in plan.conflicts] == ["run-ok-1"]
        before = _snapshot(results_repo)
        with pytest.raises(rr.ResultsRepoError, match="conflict"):
            _mod.apply_migration(plan, results_repo)
        assert _snapshot(results_repo) == before  # run-ok-2 not written, index untouched
        assert _mod.main(["--results-repo", str(results_repo)], repo_root=bench_root) == 1
        assert _snapshot(results_repo) == before

    def test_partial_migration_then_exact_rerun_is_byte_identical(
        self, bench_root: Path, results_repo: Path
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        write_legacy_run(bench_root, "img-a", "run-ok-2")
        first = _mod.plan_migration(bench_root, results_repo)
        # An interrupted apply: only the first record landed, no index rebuild.
        rr.write_run_record(results_repo, first.planned[0].record)
        resume = _mod.plan_migration(bench_root, results_repo)
        assert resume.conflicts == []
        assert [p.already_present for p in resume.planned] == [True, False]
        written = _mod.apply_migration(resume, results_repo)
        assert [p.name for p in written] == ["run-ok-2"]
        after = _snapshot(results_repo)
        rerun = _mod.plan_migration(bench_root, results_repo)
        assert _mod.apply_migration(rerun, results_repo) == []
        assert _snapshot(results_repo) == after

    def test_main_reports_conflicts_and_dry_run_flags_them(
        self, bench_root: Path, results_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_legacy_run(bench_root, "img-a", "run-ok-1")
        (results_repo / "results" / "img-a" / "run-ok-1").mkdir(parents=True)
        code = _mod.main(["--results-repo", str(results_repo), "--dry-run"], repo_root=bench_root)
        assert code == 1
        out, err = capsys.readouterr()
        assert "CONFLICTS — 1 existing record(s) disagree" in out
        assert "img-a/run-ok-1" in out
        assert "1 migration conflict(s); nothing written" in err


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def plan(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """The migration plan over the real corpus (built once per module)."""
    if not _mod.discover_legacy_runs(REPO_ROOT):
        pytest.skip("legacy docker/*/validated_results/ corpus is gone (retired by #66)")
    return _mod.plan_migration(REPO_ROOT, tmp_path_factory.mktemp("results-clone"))


class TestRealCorpusExpectations:
    """Pin the survey facts the issue records; the migrator must reproduce them."""

    def test_82_runs_79_records_3_known_skips(self, plan: Any) -> None:
        assert len(plan.planned) + len(plan.skipped) == 82
        assert len(plan.planned) == 79
        assert {s.legacy.run for s in plan.skipped} == KNOWN_SKIPPED
        assert all("missing run_manifest.json" in s.reason for s in plan.skipped)

    def test_every_record_is_legacy_sos(self, plan: Any) -> None:
        for planned in plan.planned:
            record = planned.record
            record.validate()
            assert record.mode == "legacy"
            assert record.benchmark == "sos"
            assert record.candidate.scheme == "legacy"
            assert record.candidate.verified is False
            assert record.proposal_status is None
            assert rr.candidate_hash(record.candidate) == planned.legacy.image
            assert record.artifact_pointers[0]["location"] == planned.legacy.location

    def test_77_valid_2_invalid_with_notes(self, plan: Any) -> None:
        valid = [p.record.run_id for p in plan.planned if p.record.leaderboard_valid]
        invalid = {
            p.record.run_id: p.record for p in plan.planned if not p.record.leaderboard_valid
        }
        assert len(valid) == 77
        assert set(invalid) == KNOWN_INVALID
        for record in invalid.values():
            assert "scored card set (271 cards)" in record.run_metadata["validity_note"]
            assert record.run_metadata["scored_card_count"] == 271

    def test_exactly_one_resume_leg_and_it_is_one_of_the_invalid_runs(self, plan: Any) -> None:
        resumed = [p.record for p in plan.planned if p.record.resumed_from]
        assert [r.run_id for r in resumed] == ["sos-copilot-claude-opus-4.6-2026-05-26T17-17"]
        assert "Resume Leg" in resumed[0].run_metadata["validity_note"]
        assert resumed[0].leaderboard_valid is False

    def test_the_older_cards_key_manifests_still_validate(self, plan: Any) -> None:
        from_summary = [
            p.record
            for p in plan.planned
            if p.record.run_metadata["budget_seconds_source"] == "run_summary"
        ]
        assert len(from_summary) == 4
        assert all(r.leaderboard_valid for r in from_summary)
        assert all(r.run_metadata["card_filter"] is not None for r in from_summary)
