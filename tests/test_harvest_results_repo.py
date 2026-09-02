"""Harvest retarget tests — ``harvest_validated_results.py --results-repo`` (#63 Part B, item 6).

The Harvested Results rows produced from the migrated results repo must be
identical to the rows produced by the legacy ``docker/`` walk for the same
corpus: same discovery order, same ``image`` column (the legacy identity), same
per-node and legacy rollup rows.  Filters behave identically on both paths.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from silverquillm import results_repo as rr

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


harvest_mod = _load_script("harvest_validated_results")
migrate_mod = _load_script("migrate_validated_results")

SOS_CONFIG_TEXT = (REPO_ROOT / "benchmarks" / "sos" / "config.json").read_text()
LEGACY_FILTER = ["1", "4", "13", "57", "97", "120", "201", "226", "245", "257"]
SOS_10 = [f"sos_{n}" for n in LEGACY_FILTER]


# ---------------------------------------------------------------------------
# Fixture: a small legacy corpus with modern and legacy result.json shapes
# ---------------------------------------------------------------------------


def _write_run_metadata(
    run_dir: Path, *, image: str, scored: list[str], resumed_from: str | None = None
) -> None:
    manifest: dict[str, Any] = {
        "timeout_seconds": 360000,
        "deadline_utc": "2026-06-15T13:35:05Z",
        "docker_image": f"silverquillm-{image}:latest",
        "card_filter": list(LEGACY_FILTER),
        "benchmark_set": "sos",
    }
    if resumed_from:
        manifest["resumed_from"] = resumed_from
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest))
    summary: dict[str, Any] = {
        "docker_image": manifest["docker_image"],
        "run_metadata": {
            "image": manifest["docker_image"],
            "timestamp": "2026-06-11T10:12:45Z",
            "card_count": 10,
            "timeout_seconds": 360000,
            "harness_version": "abc",
        },
        "sos_card_correctness": {
            "audited_pass_rate": 0.5,
            "card_pass_rate": 0.2,
            "cards_completed": 10,
            "cards_no_output": 0,
            "cards_timed_out": 0,
        },
        "fdn_regression": {"fdn_test_pass_rate": 1.0, "fdn_card_pass_rate": 1.0},
        "engine_regression": {"engine_test_pass_rate": 1.0, "engine_churn_lines": 0},
        "per_card": [],
        "run_status": "completed",
        "wall_clock_seconds": 1.0,
        "card_filter": list(LEGACY_FILTER),
    }
    if resumed_from:
        summary["resumed_from"] = resumed_from
    (run_dir / "run_summary.json").write_text(json.dumps(summary))
    (run_dir / "eval_result.json").write_text(
        json.dumps(
            {
                "sos_results": {
                    c: {"tests_passed": 1, "tests_failed": 0, "tests_total": 1} for c in scored
                },
                "fdn_results": {},
                "engine_result": {},
            }
        )
    )


def build_corpus(bench_root: Path) -> None:
    """Two images, three runs; modern per-node cards, one legacy card, one unreadable card."""
    (bench_root / "benchmarks" / "sos").mkdir(parents=True)
    (bench_root / "benchmarks" / "sos" / "config.json").write_text(SOS_CONFIG_TEXT)

    def run_dir(image: str, run: str) -> Path:
        d = bench_root / "docker" / image / "validated_results" / run
        d.mkdir(parents=True)
        return d

    # img-alpha / run-1: two modern cards, mixed outcomes, one with complexity_tier
    d = run_dir("img-alpha", "sos-img-alpha-2026-06-01T00-00")
    _write_run_metadata(d, image="img-alpha", scored=SOS_10)
    c = d / "cards" / "sos_1"
    c.mkdir(parents=True)
    (c / "result.json").write_text(
        json.dumps(
            {
                "tests_passed": 1,
                "tests_failed": 1,
                "tests_total": 2,
                "tests_hash": "abc123",
                "test_nodes": [
                    {"test_node": "tests.py::test_add", "outcome": "pass"},
                    {"test_node": "tests.py::test_sub", "outcome": "fail"},
                ],
            }
        )
    )
    (c / "card_spec.json").write_text(json.dumps({"complexity_tier": "medium"}))
    c = d / "cards" / "sos_4"
    c.mkdir(parents=True)
    (c / "result.json").write_text(
        json.dumps(
            {
                "tests_passed": 2,
                "tests_failed": 0,
                "tests_total": 2,
                "tests_hash": "def456",
                "test_nodes": [
                    {"test_node": "tests.py::test_mul", "outcome": "pass"},
                    {"test_node": "tests.py::test_div", "outcome": "pass"},
                ],
            }
        )
    )

    # img-alpha / run-2: a legacy card (no test_nodes; errors) and an unreadable one
    d = run_dir("img-alpha", "sos-img-alpha-2026-06-02T00-00")
    _write_run_metadata(d, image="img-alpha", scored=SOS_10)
    c = d / "cards" / "sos_1"
    c.mkdir(parents=True)
    (c / "result.json").write_text(
        json.dumps(
            {
                "tests_passed": 3,
                "tests_failed": 1,
                "tests_total": 4,
                "errors": ["FAILED /tmp/eval_sos_x/tests.py::test_boom - AssertionError"],
            }
        )
    )
    c = d / "cards" / "sos_4"
    c.mkdir(parents=True)
    (c / "result.json").write_text("{not json")

    # img-beta / run-3: a Resume Leg (invalid) — still harvested
    d = run_dir("img-beta", "sos-img-beta-2026-06-03T00-00")
    _write_run_metadata(
        d, image="img-beta", scored=SOS_10, resumed_from="sos-img-beta-2026-06-02T00-00"
    )
    c = d / "cards" / "sos_13"
    c.mkdir(parents=True)
    (c / "result.json").write_text(
        json.dumps(
            {
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_total": 1,
                "tests_hash": "beta",
                "test_nodes": [{"test_node": "tests.py::test_one", "outcome": "pass"}],
            }
        )
    )

    # img-gamma: only a results/ working dir — never a Validated Result
    (bench_root / "docker" / "img-gamma" / "results" / "run-x" / "cards" / "sos_1").mkdir(
        parents=True
    )


@pytest.fixture
def corpus(tmp_path: Path) -> tuple[Path, Path]:
    """``(bench_root, results_repo)`` with the fixture corpus migrated."""
    bench_root = tmp_path / "bench"
    build_corpus(bench_root)
    results_repo = tmp_path / "results-clone"
    rr.init_results_repo(results_repo)
    plan = migrate_mod.plan_migration(bench_root, results_repo)
    assert not plan.skipped
    migrate_mod.apply_migration(plan, results_repo)
    return bench_root, results_repo


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Equivalence
# ---------------------------------------------------------------------------


class TestHarvestEquivalence:
    def test_rows_from_results_repo_equal_rows_from_legacy_walk(
        self, corpus: tuple[Path, Path]
    ) -> None:
        bench_root, results_repo = corpus
        stamp = "2026-09-02T00:00:00+00:00"
        legacy_out = bench_root / "legacy.jsonl"
        repo_out = bench_root / "repo.jsonl"

        n_legacy = harvest_mod.harvest(bench_root, output=str(legacy_out), harvested_at=stamp)
        n_repo = harvest_mod.harvest(
            bench_root, output=str(repo_out), harvested_at=stamp, results_repo=results_repo
        )

        legacy_rows = _read_jsonl(legacy_out)
        repo_rows = _read_jsonl(repo_out)
        assert n_legacy == n_repo == len(legacy_rows) > 0
        assert legacy_rows == repo_rows
        outcomes = {r["outcome"] for r in repo_rows}
        assert outcomes == {"pass", "fail", "rollup"}
        assert {r["image"] for r in repo_rows} == {"img-alpha", "img-beta"}
        assert any(r["complexity_tier"] == "medium" for r in repo_rows)

    def test_discovery_order_and_card_dirs_match(self, corpus: tuple[Path, Path]) -> None:
        bench_root, results_repo = corpus
        legacy = harvest_mod.discover_validated_runs(bench_root)
        repo = harvest_mod.discover_validated_runs(bench_root, results_repo=results_repo)
        assert [(v.image, v.run) for v in legacy] == [(v.image, v.run) for v in repo]
        assert [v.run_dir.resolve() for v in legacy] == [v.run_dir.resolve() for v in repo]
        assert [[c.name for c in v.card_dirs] for v in legacy] == [
            [c.name for c in v.card_dirs] for v in repo
        ]

    @pytest.mark.parametrize(
        "filters",
        [
            {"image": "img-alpha"},
            {"run": "sos-img-beta-2026-06-03T00-00"},
            {"card": "sos_4"},
            {"image": "img-alpha", "card": "sos_13"},
            {"image": "nope"},
        ],
    )
    def test_filters_behave_identically(
        self, corpus: tuple[Path, Path], filters: dict[str, str]
    ) -> None:
        bench_root, results_repo = corpus
        legacy = harvest_mod.discover_validated_runs(bench_root, **filters)
        repo = harvest_mod.discover_validated_runs(bench_root, results_repo=results_repo, **filters)
        assert [(v.image, v.run, [c.name for c in v.card_dirs]) for v in legacy] == [
            (v.image, v.run, [c.name for c in v.card_dirs]) for v in repo
        ]


# ---------------------------------------------------------------------------
# Results-repo-specific behavior
# ---------------------------------------------------------------------------


class TestResultsRepoDiscovery:
    def test_record_without_legacy_tree_pointer_is_not_harvested(
        self, corpus: tuple[Path, Path]
    ) -> None:
        bench_root, results_repo = corpus
        smoke = rr.RunRecord(
            run_id="smoke-vanilla-2026-09-02T00-00",
            candidate=rr.CandidateIdentity.legacy("vanilla-claude"),
            mode="basic",
            benchmark="smoke",
            budget_seconds=600,
            leaderboard_valid=False,
            resumed_from=None,
            run_metadata={},
            proposal_status="applied",
            scores={"card_correctness": {}, "fdn_regression": {}, "engine_regression": {}},
            artifact_pointers=[{"kind": "artifact-host", "location": "s3://bucket/run"}],
        )
        rr.write_run_record(results_repo, smoke)
        runs = harvest_mod.discover_validated_runs(bench_root, results_repo=results_repo)
        assert "smoke-vanilla-2026-09-02T00-00" not in {v.run for v in runs}
        assert len(runs) == 3

    def test_missing_legacy_location_is_warned_and_skipped(
        self, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        bench_root, results_repo = corpus
        gone = bench_root / "docker" / "img-beta"
        for p in sorted(gone.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        gone.rmdir()
        runs = harvest_mod.discover_validated_runs(bench_root, results_repo=results_repo)
        assert {v.image for v in runs} == {"img-alpha"}
        err = capsys.readouterr().err
        assert "img-beta/sos-img-beta-2026-06-03T00-00: legacy-tree location not found" in err

    def test_empty_results_repo_discovers_nothing(self, tmp_path: Path) -> None:
        rr.init_results_repo(tmp_path / "empty")
        assert harvest_mod.discover_validated_runs(tmp_path, results_repo=tmp_path / "empty") == []


class TestCli:
    def test_parser_accepts_results_repo(self) -> None:
        args = harvest_mod._build_parser().parse_args(["--results-repo", "/x/y"])
        assert args.results_repo == Path("/x/y")
        assert harvest_mod._build_parser().parse_args([]).results_repo is None

    def test_flag_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(rr.RESULTS_REPO_ENV, "/from/env")
        assert harvest_mod._resolve_results_repo(Path("/from/flag")) == Path("/from/flag")
        assert harvest_mod._resolve_results_repo(None) == Path("/from/env")
        monkeypatch.delenv(rr.RESULTS_REPO_ENV)
        assert harvest_mod._resolve_results_repo(None) is None

    def test_main_reports_the_results_repo_source(
        self,
        corpus: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bench_root, results_repo = corpus
        out_path = bench_root / "out.jsonl"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "harvest_validated_results.py",
                "--output",
                str(out_path),
                "--results-repo",
                str(results_repo),
            ],
        )
        harvest_mod.main(repo_root=bench_root)
        out = capsys.readouterr().out
        assert f"Discovered 3 validated run(s) from results repo {results_repo}" in out
        assert out_path.is_file()
