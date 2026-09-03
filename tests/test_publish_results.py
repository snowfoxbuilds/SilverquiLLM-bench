"""``scripts/publish_results.py`` — the publish gate (#66 Part A).

A temporary Results Repo holds records under fixture candidates; a temporary
``candidates/`` tree holds the promoted copies.  The tests prove:
traceability is a hard refusal (absent candidate, tampered candidate,
identity mismatch, legacy identity), validity is a warning (publishable with
``--allow-invalid``), publication is byte-exact, idempotent, side-effect-free
on refusal and never commits, discovery of published results goes through
manifests only — and publication is a transaction: a failure at any copy,
validation, rename or rollback step leaves none of the requested records
(pre-existing identical ones untouched), an interruption after one rename is
rolled back from the journal on the next invocation, and the success summary
prints only after the commit.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from silverquillm.candidate import load_candidate_bundle, vendor_candidate
from silverquillm.results_repo import (
    CandidateIdentity,
    RunRecord,
    init_results_repo,
    write_run_record,
)
from tests.candidate_fixtures import DIGEST_B, make_candidate_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


publish_mod = _load_script("publish_results")


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    def _guard(real):
        def wrapper(args, *a, **kw):
            argv = [str(x) for x in (args if isinstance(args, (list, tuple)) else [args])]
            if "git" in argv[:1] or (argv and Path(argv[0]).name == "git"):
                raise AssertionError(f"publication ran git: {argv}")
            return real(args, *a, **kw)

        return wrapper

    for name in ("run", "Popen", "check_output", "check_call", "call"):
        monkeypatch.setattr(subprocess, name, _guard(getattr(subprocess, name)))
    monkeypatch.setattr(os, "system", lambda cmd: (_ for _ in ()).throw(AssertionError(cmd)))


def _scores(evaluated: bool = True) -> dict[str, dict]:
    block = {"pass_rate": 1.0, "tests_passed": 3, "tests_total": 3, "cards": 3, "evaluated": evaluated}
    return {"card_correctness": dict(block), "fdn_regression": dict(block), "engine_regression": dict(block)}


def _record(run_id: str, identity: CandidateIdentity, *, valid: bool = True, **metadata) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        candidate=identity,
        mode="basic",
        benchmark="smoke",
        budget_seconds=3600,
        leaderboard_valid=valid,
        resumed_from=metadata.pop("resumed_from", None),
        run_metadata={"run_date": "2026-09-03T00:00:00+00:00", **metadata},
        proposal_status="applied",
        scores=_scores(metadata.get("evaluated", True)),
    )


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Any]:
    """A candidates tree with one promoted candidate, and a results repo holding
    a valid run, an invalid run, and a run of an unpromoted candidate."""
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    promoted = make_candidate_dir(candidates, slug="fixture-claude")
    bundle = load_candidate_bundle(promoted)
    unpromoted = make_candidate_dir(tmp_path / "elsewhere", slug="other", digest=DIGEST_B)
    other = load_candidate_bundle(unpromoted)

    repo = tmp_path / "results-repo"
    init_results_repo(repo)
    vendor_candidate(repo, bundle)
    write_run_record(repo, _record("smoke-fixture-2026-09-03T00-00", bundle.identity))
    write_run_record(repo, _record("smoke-fixture-2026-09-03T03-00", bundle.identity))
    write_run_record(
        repo,
        _record("smoke-fixture-2026-09-03T01-00", bundle.identity, valid=False, validity_note="Resume Leg (resumed_from=prior)", resumed_from="prior"),
    )
    write_run_record(repo, _record("smoke-other-2026-09-03T02-00", other.identity))
    write_run_record(repo, _record("sos-legacy-2026-05-30T04-02", CandidateIdentity.legacy("cc-opus-48-bare")))
    return {
        "candidates": candidates,
        "promoted": promoted,
        "bundle": bundle,
        "repo": repo,
        "dest": tmp_path / "bench" / "published" / "blog-2026-09",
        "valid": "smoke-fixture-2026-09-03T00-00",
        "valid2": "smoke-fixture-2026-09-03T03-00",
        "invalid": "smoke-fixture-2026-09-03T01-00",
        "untraceable": "smoke-other-2026-09-03T02-00",
        "legacy": "sos-legacy-2026-05-30T04-02",
    }


def _plan(world: dict[str, Any], run_ids: list[str], **kwargs):
    kwargs.setdefault("allow_invalid", False)
    return publish_mod.plan_publication(
        run_ids,
        results_repo=world["repo"],
        dest=world["dest"],
        candidates_dir=world["candidates"],
        **kwargs,
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


class TestTraceability:
    def test_a_traceable_valid_run_stages_byte_for_byte(self, world, no_git) -> None:
        plan = _plan(world, [world["valid"]])
        assert plan.refusals == [] and plan.warnings == []
        assert plan.runs[0].traceability.candidate_dir == world["promoted"]
        assert plan.runs[0].traceability.vendored_copy_verified is True
        written = publish_mod.stage_publication(plan)
        dest = world["dest"] / world["valid"]
        assert sorted(p.name for p in written) == ["manifest.json", "scores.json"]
        source = plan.runs[0].source_dir
        for name in ("manifest.json", "scores.json"):
            assert (dest / name).read_bytes() == (source / name).read_bytes()

    def test_an_unpromoted_candidate_is_a_hard_refusal(self, world, no_git) -> None:
        plan = _plan(world, [world["untraceable"]])
        assert any("untraceable" in r and "promote the candidate first" in r for r in plan.refusals)
        with pytest.raises(publish_mod.PublicationRefused):
            publish_mod.stage_publication(plan)
        assert _tree(world["dest"]) == {}

    def test_a_legacy_identity_is_a_hard_refusal(self, world, no_git) -> None:
        plan = _plan(world, [world["legacy"]])
        assert any("has no Candidate Bundle" in r for r in plan.refusals)
        assert _tree(world["dest"]) == {}

    def test_a_tampered_checked_in_candidate_is_a_hard_refusal(self, world, no_git) -> None:
        dockerfile = world["promoted"] / "bundle" / "Dockerfile"
        dockerfile.write_text(dockerfile.read_text() + "RUN echo tampered\n")
        plan = _plan(world, [world["valid"]])
        assert any("fails verification" in r for r in plan.refusals)
        assert _tree(world["dest"]) == {}

    def test_a_candidate_whose_identity_differs_from_the_record_is_refused(self, world, no_git, tmp_path: Path) -> None:
        # Rename another identity's directory to carry the record's hash8 suffix.
        impostor = make_candidate_dir(tmp_path / "imp", slug="fixture-claude", digest=DIGEST_B)
        import shutil

        shutil.rmtree(world["promoted"])
        shutil.copytree(impostor, world["promoted"])
        plan = _plan(world, [world["valid"]])
        assert plan.refusals and all("untraceable" in r for r in plan.refusals)
        assert _tree(world["dest"]) == {}

    def test_a_tampered_vendored_copy_in_the_results_repo_is_refused(self, world, no_git) -> None:
        from silverquillm.results_repo import candidate_copy_dir

        copy = candidate_copy_dir(world["repo"], world["bundle"].identity)
        (copy / "Dockerfile").write_text((copy / "Dockerfile").read_text() + "RUN echo x\n")
        plan = _plan(world, [world["valid"]])
        assert any("vendored candidate copy" in r for r in plan.refusals)

    def test_an_unknown_or_ambiguous_run_id_refuses(self, world, no_git) -> None:
        with pytest.raises(publish_mod.PublicationRefused, match="no run record"):
            _plan(world, ["nope"])
        with pytest.raises(publish_mod.PublicationRefused, match="repeat"):
            _plan(world, [world["valid"], world["valid"]])


class TestValidity:
    def test_invalid_is_a_warning_refused_without_the_flag(self, world, no_git) -> None:
        plan = _plan(world, [world["invalid"]])
        assert any("Resume Leg" in w for w in plan.warnings)
        assert any("--allow-invalid" in r for r in plan.refusals)
        assert plan.runs[0].traceability is not None  # traceable — validity is the only objection
        assert _tree(world["dest"]) == {}

    def test_allow_invalid_publishes_with_the_warning(self, world, no_git) -> None:
        plan = _plan(world, [world["invalid"]], allow_invalid=True)
        assert plan.refusals == [] and plan.warnings
        publish_mod.stage_publication(plan)
        manifest = json.loads((world["dest"] / world["invalid"] / "manifest.json").read_text())
        assert manifest["leaderboard_valid"] is False  # the flag travels; tooling filters on it

    def test_validity_warnings_name_every_reason(self) -> None:
        identity = CandidateIdentity.legacy("img")
        record = _record("r", identity, valid=False, validity_note="scored card set differs", evaluated=False, failure={"class": "timeout", "phase": "agent"})
        reasons = publish_mod.validity_warnings(record)
        assert any("scored card set differs" in r for r in reasons)
        assert any("never evaluated" in r for r in reasons)
        assert any("timeout" in r for r in reasons)
        assert publish_mod.validity_warnings(_record("ok", identity)) == []


class TestStaging:
    def test_all_or_nothing_across_the_set(self, world, no_git) -> None:
        plan = _plan(world, [world["valid"], world["untraceable"]])
        assert plan.runs[0].refusals == [] and plan.runs[1].refusals
        with pytest.raises(publish_mod.PublicationRefused):
            publish_mod.stage_publication(plan)
        assert _tree(world["dest"]) == {}

    def test_idempotent_and_conflict_aware(self, world, no_git) -> None:
        publish_mod.stage_publication(_plan(world, [world["valid"]]))
        before = _tree(world["dest"])
        again = _plan(world, [world["valid"]])
        assert again.runs[0].already_staged and again.to_stage == []
        assert publish_mod.stage_publication(again) == []
        assert _tree(world["dest"]) == before
        (world["dest"] / world["valid"] / "scores.json").write_text("{}")
        conflict = _plan(world, [world["valid"]])
        assert any("different content" in r for r in conflict.refusals)

    def test_main_stages_prints_the_diff_summary_and_never_commits(self, world, no_git, capsys) -> None:
        code = publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]),
            "--candidates-dir", str(world["candidates"]), world["valid"],
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "approval stamp" in out and f"A {world['dest'] / world['valid'] / 'manifest.json'}" in out
        assert (world["dest"] / world["valid"] / "manifest.json").is_file()

    def test_main_dry_run_and_refusal_exit_codes(self, world, no_git, capsys) -> None:
        assert publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]),
            "--candidates-dir", str(world["candidates"]), "--dry-run", world["valid"],
        ]) == 0
        assert _tree(world["dest"]) == {}
        assert publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]),
            "--candidates-dir", str(world["candidates"]), world["invalid"],
        ]) == 1
        assert "REFUSED" in capsys.readouterr().out
        assert _tree(world["dest"]) == {}


def _tree_with_mtimes(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    } if root.exists() else {}


def _entries(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir()) if root.is_dir() else []


class TestTransaction:
    """Publication is all-or-nothing on disk, not only in the plan."""

    @pytest.fixture
    def prior(self, world, no_git) -> dict[str, Any]:
        """A destination already holding one identical record (must survive
        every rollback byte for byte, mtime included)."""
        publish_mod.stage_publication(_plan(world, [world["invalid"]], allow_invalid=True))
        return {"snapshot": _tree_with_mtimes(world["dest"] / world["invalid"])}

    def _assert_clean(self, world, prior) -> None:
        dest = world["dest"]
        assert _entries(dest) == [world["invalid"]], _entries(dest)
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        assert not publish_mod.journal_path(dest).exists()

    @pytest.mark.parametrize("fail_on", ["first", "second"])
    def test_a_copy_failure_leaves_no_new_final_record(self, world, prior, monkeypatch: pytest.MonkeyPatch, fail_on: str) -> None:
        real = shutil.copyfile
        target_run = world["valid"] if fail_on == "first" else world["valid2"]

        def failing(src, dst, *a, **kw):
            if Path(dst).parent.name == target_run and Path(dst).name == "scores.json":
                raise OSError(28, "No space left on device")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(shutil, "copyfile", failing)
        plan = _plan(world, [world["valid"], world["valid2"]], allow_invalid=True)
        with pytest.raises(publish_mod.PublicationRefused, match="rolled back"):
            publish_mod.stage_publication(plan)
        self._assert_clean(world, prior)

    def test_a_validation_failure_of_a_staged_copy_leaves_no_new_final_record(self, world, prior, monkeypatch: pytest.MonkeyPatch) -> None:
        real = shutil.copyfile

        def corrupting(src, dst, *a, **kw):
            real(src, dst, *a, **kw)
            if Path(dst).parent.name == world["valid2"] and Path(dst).name == "manifest.json":
                Path(dst).write_text(Path(dst).read_text() + "\n")  # one byte off

        monkeypatch.setattr(shutil, "copyfile", corrupting)
        with pytest.raises(publish_mod.PublicationRefused, match="byte for byte"):
            publish_mod.stage_publication(_plan(world, [world["valid"], world["valid2"]], allow_invalid=True))
        self._assert_clean(world, prior)

    def test_a_rename_failure_rolls_back_the_records_already_committed(self, world, prior, monkeypatch: pytest.MonkeyPatch) -> None:
        real = os.rename
        renames: list[str] = []

        def failing(src, dst, *a, **kw):
            renames.append(Path(dst).name)
            if Path(dst).name == world["valid2"]:
                raise OSError(5, "Input/output error")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(os, "rename", failing)
        with pytest.raises(publish_mod.PublicationRefused) as info:
            publish_mod.stage_publication(_plan(world, [world["valid"], world["valid2"]], allow_invalid=True))
        assert renames == [world["valid"], world["valid2"]], "the first record had been committed"
        assert f"removed {world['valid']}" in str(info.value)
        self._assert_clean(world, prior)

    def test_an_interruption_after_one_rename_is_recovered_from_the_journal(self, world, prior, capsys) -> None:
        plan = _plan(world, [world["valid"], world["valid2"]], allow_invalid=True)
        tx = publish_mod.PublicationTransaction(plan)
        tx.begin()
        tx.stage()
        tx.commit_one(tx.runs[0])
        # ... and the process dies here: one record in place, one in staging, journal present.
        dest = world["dest"]
        assert (dest / world["valid"] / "manifest.json").is_file()
        assert publish_mod.journal_path(dest).exists()
        journal = json.loads(publish_mod.journal_path(dest).read_text())
        assert journal["committed"] == [world["valid"]] and journal["planned"] == [world["valid"], world["valid2"]]
        # A new plan refuses until recovery ran.
        with pytest.raises(publish_mod.PublicationRefused, match="interrupted"):
            _plan(world, [world["valid2"]])
        report = publish_mod.recover_publication(dest)
        assert report is not None and report.action == "rolled-back" and report.records == (world["valid"],)
        self._assert_clean(world, prior)
        assert publish_mod.recover_publication(dest) is None
        # The next invocation publishes the whole set cleanly.
        code = publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(dest), "--candidates-dir", str(world["candidates"]),
            "--allow-invalid", world["valid"], world["valid2"],
        ])
        assert code == 0
        assert sorted(_entries(dest)) == sorted([world["invalid"], world["valid"], world["valid2"]])

    def test_main_recovers_an_interrupted_transaction_before_planning(self, world, prior, capsys) -> None:
        plan = _plan(world, [world["valid"], world["valid2"]])
        tx = publish_mod.PublicationTransaction(plan)
        tx.begin()
        tx.stage()
        tx.commit_one(tx.runs[0])  # valid is in place, valid2 still in staging: the process dies here
        code = publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]), "--candidates-dir", str(world["candidates"]),
            world["valid2"],
        ])
        out = capsys.readouterr().out
        assert code == 0 and out.startswith("RECOVERED") and "rolling it back" in out and world["valid"] in out
        assert _entries(world["dest"]) == sorted([world["invalid"], world["valid2"]])

    def test_a_fully_committed_transaction_whose_journal_survived_is_completed(self, world, prior) -> None:
        plan = _plan(world, [world["valid"]])
        tx = publish_mod.PublicationTransaction(plan)
        tx.begin()
        tx.stage()
        tx.commit()
        # ... dies before finish(): every record is in place.
        report = publish_mod.recover_publication(world["dest"])
        assert report is not None and report.action == "completed"
        assert _entries(world["dest"]) == sorted([world["invalid"], world["valid"]])
        assert not publish_mod.journal_path(world["dest"]).exists()

    def test_an_interrupted_rename_whose_journal_did_not_catch_up_is_rolled_back(self, world, prior) -> None:
        plan = _plan(world, [world["valid"]])
        tx = publish_mod.PublicationTransaction(plan)
        tx.begin()
        tx.stage()
        # Journal says "committing", the rename landed, the journal was never updated.
        tx.journal.committing = world["valid"]
        publish_mod._write_journal(tx.journal_path, tx.journal)
        os.rename(tx.staging / world["valid"], world["dest"] / world["valid"])
        report = publish_mod.recover_publication(world["dest"])
        assert report is not None and report.records == (world["valid"],)
        self._assert_clean(world, prior)

    def test_a_failed_rollback_is_reported_and_blocks_further_publication(self, world, prior, monkeypatch: pytest.MonkeyPatch) -> None:
        real_rename = os.rename
        real_rmtree = shutil.rmtree

        def failing_rename(src, dst, *a, **kw):
            if Path(dst).name == world["valid2"]:
                raise OSError(5, "Input/output error")
            return real_rename(src, dst, *a, **kw)

        def failing_rmtree(path, *a, **kw):
            if Path(path).name == world["valid"]:
                raise OSError(1, "Operation not permitted")
            return real_rmtree(path, *a, **kw)

        monkeypatch.setattr(os, "rename", failing_rename)
        monkeypatch.setattr(shutil, "rmtree", failing_rmtree)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="rollback failed"):
            publish_mod.stage_publication(_plan(world, [world["valid"], world["valid2"]], allow_invalid=True))
        assert publish_mod.journal_path(world["dest"]).exists(), "the journal stays for the operator"
        monkeypatch.undo()
        with pytest.raises(publish_mod.PublicationRefused, match="interrupted"):
            _plan(world, [world["valid2"]])
        assert publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]), "--candidates-dir", str(world["candidates"]),
            world["valid2"],
        ]) == 0  # recovery now succeeds; the journal is gone and publication proceeds
        assert not publish_mod.journal_path(world["dest"]).exists()

    def test_the_success_summary_prints_only_after_the_commit(self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        real = shutil.copyfile

        def failing(src, dst, *a, **kw):
            if Path(dst).parent.name == world["valid2"]:
                raise OSError(28, "No space left on device")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(shutil, "copyfile", failing)
        code = publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]), "--candidates-dir", str(world["candidates"]),
            world["valid"], world["valid2"],
        ])
        captured = capsys.readouterr()
        assert code == 1 and "rolled back" in captured.err
        assert "  A " not in captured.out and "approval stamp" not in captured.out
        self._assert_clean(world, prior)

    def test_mixed_identical_and_new_records_publish_together(self, world, prior) -> None:
        plan = _plan(world, [world["invalid"], world["valid"], world["valid2"]], allow_invalid=True)
        assert [run.already_staged for run in plan.runs] == [True, False, False]
        written = publish_mod.stage_publication(plan)
        assert sorted(p.parent.name for p in written) == sorted([world["valid"], world["valid"], world["valid2"], world["valid2"]])
        assert _tree_with_mtimes(world["dest"] / world["invalid"]) == prior["snapshot"]
        assert not publish_mod.journal_path(world["dest"]).exists()
        assert not any(name.startswith(".publish") for name in _entries(world["dest"]))


class TestDiscovery:
    def test_published_results_are_discovered_by_manifest_wherever_they_sit(self, world, no_git, tmp_path: Path) -> None:
        root = tmp_path / "bench" / "published"
        publish_mod.stage_publication(_plan(world, [world["valid"]]))
        deep = tmp_path / "bench" / "published" / "experiments" / "x" / "y"
        publish_mod.stage_publication(
            publish_mod.plan_publication(
                [world["invalid"]], results_repo=world["repo"], dest=deep,
                candidates_dir=world["candidates"], allow_invalid=True,
            )
        )
        (root / "notes").mkdir()
        (root / "notes" / "README.md").write_text("no manifest here\n")
        found = {run_dir.name: record for run_dir, record in publish_mod.iter_published_records(root)}
        assert set(found) == {world["valid"], world["invalid"]}
        assert found[world["valid"]].leaderboard_valid is True
        assert found[world["invalid"]].leaderboard_valid is False

    def test_a_misplaced_manifest_raises_instead_of_misattributing(self, world, no_git) -> None:
        publish_mod.stage_publication(_plan(world, [world["valid"]]))
        staged = world["dest"] / world["valid"]
        staged.rename(world["dest"] / "renamed")
        with pytest.raises(Exception, match="does not match the directory name"):
            list(publish_mod.iter_published_records(world["dest"]))
