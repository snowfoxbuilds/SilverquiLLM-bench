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
prints only after the commit.  Recovery is contained: a journal naming
anything that is not a plain immediate child of the destination, or a
cleanup target that is a symlink or holds what the transaction did not
create, is refused with the tree unchanged; ``--dry-run`` is strictly
read-only, reporting a pending recovery without performing it.  Wherever the
gate establishes that a candidate or a record is present in a tree, the
entry is proven by ``lstat``: a symlinked candidate wrapper or bundle, a
symlinked source record, a symlinked destination record with identical
bytes and a symlinked published record are refused, never followed, with
every tree unchanged.
"""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
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


@pytest.fixture
def prior(world, no_git) -> dict[str, Any]:
    """A destination already holding one identical record (must survive
    every rollback byte for byte, mtime included)."""
    publish_mod.stage_publication(_plan(world, [world["invalid"]], allow_invalid=True))
    return {"snapshot": _tree_with_mtimes(world["dest"] / world["invalid"])}


class TestTransaction:
    """Publication is all-or-nothing on disk, not only in the plan."""

    def _assert_clean(self, world, prior) -> None:
        dest = world["dest"]
        assert _entries(dest) == [world["invalid"]], _entries(dest)
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        assert not publish_mod.journal_path(dest).exists()

    @pytest.mark.parametrize("fail_on", ["first", "second"])
    def test_a_copy_failure_leaves_no_new_final_record(self, world, prior, monkeypatch: pytest.MonkeyPatch, fail_on: str) -> None:
        real = publish_mod._copy_regular_file
        target_run = world["valid"] if fail_on == "first" else world["valid2"]

        def failing(src, dst, *a, **kw):
            if Path(dst).parent.name == target_run and Path(dst).name == "scores.json":
                raise OSError(28, "No space left on device")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(publish_mod, "_copy_regular_file", failing)
        plan = _plan(world, [world["valid"], world["valid2"]], allow_invalid=True)
        with pytest.raises(publish_mod.PublicationRefused, match="rolled back"):
            publish_mod.stage_publication(plan)
        self._assert_clean(world, prior)

    def test_a_validation_failure_of_a_staged_copy_leaves_no_new_final_record(self, world, prior, monkeypatch: pytest.MonkeyPatch) -> None:
        real = publish_mod._copy_regular_file

        def corrupting(src, dst, *a, **kw):
            real(src, dst, *a, **kw)
            if Path(dst).parent.name == world["valid2"] and Path(dst).name == "manifest.json":
                Path(dst).write_text(Path(dst).read_text() + "\n")  # one byte off

        monkeypatch.setattr(publish_mod, "_copy_regular_file", corrupting)
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
        real = publish_mod._copy_regular_file

        def failing(src, dst, *a, **kw):
            if Path(dst).parent.name == world["valid2"]:
                raise OSError(28, "No space left on device")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(publish_mod, "_copy_regular_file", failing)
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


def _snapshot(root: Path) -> dict[str, tuple[Any, ...]]:
    """Every entry under *root* — files, directories, symlinks — with mode,
    mtime and content or link target: what a read-only step must leave
    exactly as it found it."""
    out: dict[str, tuple[Any, ...]] = {}
    for p in [root, *sorted(root.rglob("*"))]:
        st = p.lstat()
        payload = os.readlink(p) if p.is_symlink() else (p.read_bytes() if p.is_file() else None)
        out["." if p == root else str(p.relative_to(root))] = (st.st_mode, st.st_mtime_ns, payload)
    return out


def _replace_with_directory(path: Path) -> Path:
    """*path* becomes a directory holding one foreign file — what a corrupted
    or hostile record file could hide.  Returns the nested file."""
    path.unlink()
    path.mkdir()
    nested = path / "nested.txt"
    nested.write_text("foreign\n")
    return nested


def _replace_with_symlink(path: Path, target: Path) -> None:
    path.unlink()
    path.symlink_to(target)


def _replace_with_file(path: Path) -> None:
    shutil.rmtree(path)
    path.write_text("not a directory\n")


def _replace_with_directory_symlink(path: Path, target: Path) -> None:
    shutil.rmtree(path)
    path.symlink_to(target)


def _journal_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1, "staging": ".publish-staging-0123abcd", "planned": ["r1", "r2"],
        "committing": None, "committed": ["r1"],
    }
    payload.update(overrides)
    return payload


class TestJournalContainment:
    """Recovery removes only what the journal proves the transaction created —
    never anything outside the destination, never through a symlink — and a
    journal that fails the proof leaves the destination exactly as it was."""

    @pytest.fixture
    def arena(self, world, prior) -> dict[str, Any]:
        dest = world["dest"]
        sentinel = dest.parent / "sentinel"
        sentinel.mkdir()
        (sentinel / "keep.txt").write_text("keep\n")
        return {"dest": dest, "sentinel": sentinel, "root": dest.parent}

    @staticmethod
    def _write_journal(dest: Path, payload: dict[str, Any] | str) -> Path:
        path = publish_mod.journal_path(dest)
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
        return path

    def _assert_refused_without_mutation(self, arena: dict[str, Any], *, match: str) -> None:
        before = _snapshot(arena["root"])
        with pytest.raises(publish_mod.PublicationRecoveryError, match=match):
            publish_mod.recover_publication(arena["dest"])
        assert _snapshot(arena["root"]) == before, "recovery changed the tree"
        with pytest.raises(publish_mod.PublicationRecoveryError, match=match):
            publish_mod.inspect_publication(arena["dest"])
        assert _snapshot(arena["root"]) == before, "inspection changed the tree"
        assert (arena["sentinel"] / "keep.txt").read_text() == "keep\n"
        assert publish_mod.journal_path(arena["dest"]).exists(), "the journal stays for the operator"

    def test_a_symlinked_journal_naming_an_existing_record_grants_no_deletion_authority(self, world, prior, arena, capsys) -> None:
        """The journal is the one thing that authorizes recovery to delete.
        Here its path is a symlink to an external journal that parses, names
        the pre-existing published record as committed and a second record
        as still planned — trusted, it would roll the existing record back.
        Recovery and inspection refuse it as a symlink, and the record, the
        staging tree, the external target, the link, every byte and every
        mtime stay exactly as they were."""
        dest = arena["dest"]
        staging = dest / ".publish-staging-0123abcd"
        (staging / "r2").mkdir(parents=True)
        (staging / "r2" / "manifest.json").write_text("{}\n")
        external = arena["root"] / "elsewhere" / "journal.json"
        external.parent.mkdir()
        external.write_text(json.dumps(_journal_payload(planned=[world["invalid"], "r2"], committed=[world["invalid"]])))
        parsed = publish_mod.Journal.from_dict(json.loads(external.read_text()))
        assert not parsed.complete and parsed.committed == [world["invalid"]], "trusted, it would remove the record"
        publish_mod.journal_path(dest).symlink_to(external)
        self._assert_refused_without_mutation(arena, match="is a symlink")
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        assert os.readlink(publish_mod.journal_path(dest)) == str(external)
        before = _snapshot(arena["root"])
        argv = ["--results-repo", str(world["repo"]), "--dest", str(dest), "--candidates-dir", str(world["candidates"]), world["valid"]]
        assert publish_mod.main(argv) == 2
        assert "RECOVERY FAILED" in capsys.readouterr().err
        assert publish_mod.main([*argv, "--dry-run"]) == 2
        assert "would FAIL" in capsys.readouterr().err
        assert _snapshot(arena["root"]) == before

    def test_a_dangling_journal_symlink_is_refused_not_treated_as_absent(self, world, arena) -> None:
        publish_mod.journal_path(arena["dest"]).symlink_to(arena["root"] / "nowhere.json")
        before = _snapshot(arena["root"])
        for step in (publish_mod.recover_publication, publish_mod.inspect_publication):
            with pytest.raises(publish_mod.PublicationRecoveryError, match="is a symlink"):
                step(arena["dest"])
        with pytest.raises(publish_mod.PublicationRefused, match="exists"):
            _plan(world, [world["valid"]])
        assert _snapshot(arena["root"]) == before

    @pytest.mark.parametrize("kind", ["directory", "FIFO"])
    def test_a_journal_that_is_not_a_regular_file_is_refused(self, arena, kind: str) -> None:
        path = publish_mod.journal_path(arena["dest"])
        if kind == "directory":
            path.mkdir()
            (path / "journal.json").write_text(json.dumps(_journal_payload()))
        else:
            os.mkfifo(path)
        self._assert_refused_without_mutation(arena, match=f"is a {kind}, not a regular file")

    def test_a_traversal_in_staging_cannot_delete_a_sibling_directory(self, world, arena) -> None:
        # A "complete" journal: recovery would remove exactly the staging directory it names.
        self._write_journal(arena["dest"], _journal_payload(staging="../sentinel", planned=[world["invalid"]], committed=[world["invalid"]]))
        self._assert_refused_without_mutation(arena, match="staging")
        # The containment guard refuses the same name even when asked directly.
        with pytest.raises(publish_mod.PublicationRecoveryError, match="plain directory name"):
            publish_mod._removable_directory(arena["dest"], "../sentinel")
        assert arena["sentinel"].is_dir()

    @pytest.mark.parametrize(
        "payload, match",
        [
            (_journal_payload(staging="/tmp/.publish-staging-0123abcd"), "staging"),
            (_journal_payload(staging=".publish-staging-0123abcd/inner"), "staging"),
            (_journal_payload(staging="."), "staging"),
            (_journal_payload(staging=".."), "staging"),
            (_journal_payload(staging=".publish-staging-XYZ"), "staging"),
            (_journal_payload(staging="../.publish-staging-0123abcd"), "staging"),
            (_journal_payload(planned=["r1", "r1"]), "repeat"),
            (_journal_payload(committed=["r1", "r1"]), "repeat"),
            (_journal_payload(committed=["r9"]), "never planned"),
            (_journal_payload(committing="r9"), "committing"),
            (_journal_payload(committing="r1"), "committing"),
            (_journal_payload(planned=["../r1", "r2"], committed=[]), "plain record"),
            (_journal_payload(planned=["/r1"], committed=[]), "plain record"),
            (_journal_payload(planned=[".r1"], committed=[]), "plain record"),
            (_journal_payload(planned=["a/b"], committed=[]), "plain record"),
            (_journal_payload(planned=["a\\b"], committed=[]), "plain record"),
            (_journal_payload(planned=[], committed=[]), "non-empty"),
            (_journal_payload(extra=1), "unexpected or missing"),
            ({k: v for k, v in _journal_payload().items() if k != "committed"}, "unexpected or missing"),
            (_journal_payload(schema_version=2), "unrecognized"),
            ("[]", "not a JSON object"),
            ("{not json", "cannot read"),
        ],
        ids=[
            "absolute-staging", "staging-separator", "staging-dot", "staging-dotdot", "staging-format",
            "staging-traversal", "planned-dup", "committed-dup", "committed-unplanned", "committing-unplanned",
            "committing-committed", "planned-traversal", "planned-absolute", "planned-dotfile",
            "planned-separator", "planned-backslash", "planned-empty", "extra-field", "missing-field",
            "version", "not-object", "not-json",
        ],
    )
    def test_malformed_journals_are_refused_without_mutation(self, arena, payload, match: str) -> None:
        self._write_journal(arena["dest"], payload)
        self._assert_refused_without_mutation(arena, match=match)

    def test_a_symlinked_staging_directory_is_refused_not_followed(self, world, arena) -> None:
        (arena["dest"] / ".publish-staging-0123abcd").symlink_to(arena["sentinel"])
        self._write_journal(arena["dest"], _journal_payload(planned=[world["invalid"]], committed=[world["invalid"]]))
        self._assert_refused_without_mutation(arena, match="symlink")

    def test_a_symlinked_record_directory_is_refused_not_followed(self, world, arena) -> None:
        dest = arena["dest"]
        (dest / "linked").symlink_to(arena["sentinel"])
        (dest / ".publish-staging-0123abcd").mkdir()
        self._write_journal(dest, _journal_payload(planned=["linked", "r2"], committed=["linked"]))
        self._assert_refused_without_mutation(arena, match="symlink")

    def test_a_record_holding_what_the_transaction_did_not_create_is_refused(self, world, arena) -> None:
        dest = arena["dest"]
        (dest / ".publish-staging-0123abcd").mkdir()
        shutil.copytree(dest / world["invalid"], dest / "r1")
        (dest / "r1" / "notes.txt").write_text("not a record file\n")
        self._write_journal(dest, _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="did not create")
        # ... and so is a staging tree holding one.
        (dest / "r1" / "notes.txt").unlink()
        (dest / ".publish-staging-0123abcd" / "stray").mkdir()
        self._assert_refused_without_mutation(arena, match="did not create")

    def test_a_record_that_is_a_plain_file_is_refused(self, world, arena) -> None:
        dest = arena["dest"]
        (dest / ".publish-staging-0123abcd").mkdir()
        (dest / "r1").write_text("not a directory\n")
        self._write_journal(dest, _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="not a directory")

    def _committed(self, world, arena, name: str) -> Path:
        """A complete committed record copied from the pre-existing one, beside
        an empty staging directory."""
        dest = arena["dest"]
        (dest / ".publish-staging-0123abcd").mkdir(exist_ok=True)
        shutil.copytree(dest / world["invalid"], dest / name)
        return dest / name

    def test_a_record_file_that_is_a_directory_is_refused_and_what_it_holds_survives(self, world, arena) -> None:
        record = self._committed(world, arena, "r1")
        nested = _replace_with_directory(record / "manifest.json")
        self._write_journal(arena["dest"], _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="manifest.json is a directory, not the regular file")
        assert nested.read_text() == "foreign\n"

    def test_a_record_file_that_is_a_special_file_is_refused(self, world, arena) -> None:
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs are not supported on this platform")
        record = self._committed(world, arena, "r1")
        (record / "scores.json").unlink()
        os.mkfifo(record / "scores.json")
        self._write_journal(arena["dest"], _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="scores.json is a FIFO, not the regular file")

    def test_a_record_file_that_is_a_symlink_is_refused_not_followed(self, world, arena) -> None:
        record = self._committed(world, arena, "r1")
        _replace_with_symlink(record / "scores.json", arena["sentinel"] / "keep.txt")
        self._write_journal(arena["dest"], _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="scores.json is a symlink, not the regular file")

    def test_a_committed_or_landed_record_must_hold_every_record_file(self, world, arena) -> None:
        record = self._committed(world, arena, "r1")
        (record / "scores.json").unlink()
        self._write_journal(arena["dest"], _journal_payload(planned=["r1", "r2"], committed=["r1"]))
        self._assert_refused_without_mutation(arena, match="lacks scores.json")
        # The rename that landed before the journal caught up is held to the same bar.
        self._write_journal(arena["dest"], _journal_payload(planned=["r1", "r2"], committing="r1", committed=[]))
        self._assert_refused_without_mutation(arena, match="lacks scores.json")

    @pytest.mark.parametrize(
        "malform, match",
        [
            (lambda staged, arena: (staged / "notes.txt").write_text("foreign\n"), "did not create"),
            (lambda staged, arena: _replace_with_directory(staged / "manifest.json"), "manifest.json is a directory"),
            (lambda staged, arena: _replace_with_symlink(staged / "scores.json", arena["sentinel"] / "keep.txt"), "scores.json is a symlink"),
            (lambda staged, arena: _replace_with_file(staged), "not a directory"),
            (lambda staged, arena: _replace_with_directory_symlink(staged, arena["sentinel"]), "is a symlink"),
        ],
        ids=["foreign-file", "manifest-directory", "scores-symlink", "record-plain-file", "record-symlink"],
    )
    def test_malformed_staged_content_is_refused(self, world, arena, malform, match: str) -> None:
        dest = arena["dest"]
        staging = dest / ".publish-staging-0123abcd"
        staging.mkdir()
        shutil.copytree(dest / world["invalid"], staging / "r2")
        malform(staging / "r2", arena)
        self._write_journal(dest, _journal_payload(planned=["r1", "r2"], committed=[]))
        self._assert_refused_without_mutation(arena, match=match)

    def test_one_target_failing_the_proof_leaves_every_target_in_place(self, world, arena) -> None:
        """The whole target set is validated before the first removal: a valid
        committed record, a valid partially staged record and the staging
        directory all survive when one committed record fails."""
        dest = arena["dest"]
        staging = dest / ".publish-staging-0123abcd"
        first = self._committed(world, arena, "r1")
        nested = _replace_with_directory(self._committed(world, arena, "r2") / "manifest.json")
        shutil.copytree(dest / world["invalid"], staging / "r3")
        (staging / "r3" / "scores.json").unlink()
        self._write_journal(dest, _journal_payload(planned=["r1", "r2", "r3"], committed=["r1", "r2"]))
        self._assert_refused_without_mutation(arena, match="manifest.json is a directory")
        assert first.is_dir() and nested.is_file() and (staging / "r3" / "manifest.json").is_file()

    def test_a_record_whose_copy_was_interrupted_is_rolled_back(self, world, prior) -> None:
        """The process can die between the two copies: a staged record holding
        only manifest.json is what the transaction created, and it goes."""
        dest = world["dest"]
        tx = publish_mod.PublicationTransaction(_plan(world, [world["valid"]]))
        tx.begin()
        assert tx.staging is not None
        staged = tx.staging / world["valid"]
        staged.mkdir()
        shutil.copyfile(tx.runs[0].source_dir / "manifest.json", staged / "manifest.json")
        report = publish_mod.inspect_publication(dest)
        assert report is not None and report.action == "rolled-back" and not report.performed
        report = publish_mod.recover_publication(dest)
        assert report is not None and report.action == "rolled-back" and report.records == () and report.performed
        assert _entries(dest) == [world["invalid"]] and _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        assert not publish_mod.journal_path(dest).exists()

    def test_valid_interrupted_and_completed_transactions_still_recover(self, world, prior) -> None:
        dest = world["dest"]
        plan = _plan(world, [world["valid"], world["valid2"]], allow_invalid=True)
        tx = publish_mod.PublicationTransaction(plan)
        tx.begin()
        tx.stage()
        tx.commit_one(tx.runs[0])
        report = publish_mod.recover_publication(dest)
        assert report is not None and report.action == "rolled-back" and report.records == (world["valid"],) and report.performed
        assert _entries(dest) == [world["invalid"]] and _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        tx = publish_mod.PublicationTransaction(_plan(world, [world["valid"]]))
        tx.begin()
        tx.stage()
        tx.commit()
        report = publish_mod.recover_publication(dest)
        assert report is not None and report.action == "completed" and report.performed
        assert _entries(dest) == sorted([world["invalid"], world["valid"]])
        assert not publish_mod.journal_path(dest).exists()


class TestDryRunIsReadOnly:
    """``--dry-run`` never recovers: it reports the recovery that would occur,
    returns nonzero, and leaves bytes and mtimes exactly as they were."""

    def _main(self, world, *run_ids: str, dry_run: bool = True) -> int:
        return publish_mod.main([
            "--results-repo", str(world["repo"]), "--dest", str(world["dest"]), "--candidates-dir", str(world["candidates"]),
            "--allow-invalid", *(["--dry-run"] if dry_run else []), *run_ids,
        ])

    def test_over_a_partial_transaction(self, world, prior, capsys) -> None:
        dest = world["dest"]
        tx = publish_mod.PublicationTransaction(_plan(world, [world["valid"], world["valid2"]], allow_invalid=True))
        tx.begin()
        tx.stage()
        tx.commit_one(tx.runs[0])
        before = _snapshot(dest)
        code = self._main(world, world["valid2"])
        out, err = capsys.readouterr()
        assert code == 1
        assert out.startswith("RECOVERY REQUIRED") and "rolled back" in out and f"would remove {world['valid']}" in out
        assert "REFUSED" in err and "changed nothing" in err and "would publish" not in out
        assert _snapshot(dest) == before, "the dry run changed the tree"
        assert self._main(world, world["valid2"]) == 1 and _snapshot(dest) == before
        # The real invocation recovers and publishes.
        assert self._main(world, world["valid2"], dry_run=False) == 0
        assert _entries(dest) == sorted([world["invalid"], world["valid2"]])

    def test_over_a_complete_transaction(self, world, prior, capsys) -> None:
        dest = world["dest"]
        tx = publish_mod.PublicationTransaction(_plan(world, [world["valid"]]))
        tx.begin()
        tx.stage()
        tx.commit()
        before = _snapshot(dest)
        code = self._main(world, world["valid"])
        out, err = capsys.readouterr()
        assert code == 1 and "had already committed every record" in out and world["valid"] in out
        assert "REFUSED" in err
        assert _snapshot(dest) == before
        report = publish_mod.recover_publication(dest)
        assert report is not None and report.action == "completed"

    def test_a_journal_recovery_would_refuse_is_reported_and_nothing_changes(self, world, prior, capsys) -> None:
        dest = world["dest"]
        publish_mod.journal_path(dest).write_text("{not json", encoding="utf-8")
        before = _snapshot(dest)
        assert self._main(world, world["valid"]) == 2
        assert "would FAIL" in capsys.readouterr().err
        assert _snapshot(dest) == before

    def test_without_a_journal_the_dry_run_writes_nothing_and_plans(self, world, no_git, capsys) -> None:
        assert self._main(world, world["valid"]) == 0
        assert "would publish" in capsys.readouterr().out
        assert not world["dest"].exists()


class TestInTreeArtifacts:
    """Wherever the gate establishes that a candidate or a record is present
    in a repository tree, it proves the entry itself by ``lstat``: a symlink
    is refused, never followed — even one that resolves to byte-identical,
    perfectly valid content — and the refusal leaves the source, candidate
    and destination trees unchanged."""

    @staticmethod
    def _twin(world, tmp_path: Path, source: Path) -> Path:
        """A valid copy of *source* outside every curated tree."""
        twin = tmp_path / "elsewhere" / source.name
        shutil.copytree(source, twin)
        return twin

    def test_a_symlinked_candidate_wrapper_is_hard_refused_not_followed(self, world, no_git, tmp_path: Path) -> None:
        twin = self._twin(world, tmp_path, world["promoted"])
        assert load_candidate_bundle(twin).candidate_hash == world["bundle"].candidate_hash  # valid on its own
        shutil.rmtree(world["promoted"])
        world["promoted"].symlink_to(twin, target_is_directory=True)
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match="is a symlink") as info:
            publish_mod.check_traceability(
                world["bundle"].identity, candidates_dir=world["candidates"], results_repo=world["repo"]
            )
        assert str(world["promoted"]) in str(info.value) and "refusing to follow" in str(info.value)
        plan = _plan(world, [world["valid"]])
        assert plan.refusals and all("untraceable" in r and "symlink" in r for r in plan.refusals)
        with pytest.raises(publish_mod.PublicationRefused):
            publish_mod.stage_publication(plan)
        assert _snapshot(tmp_path) == before

    def test_a_symlinked_bundle_inside_a_real_wrapper_is_refused(self, world, no_git, tmp_path: Path) -> None:
        twin = self._twin(world, tmp_path, world["promoted"])
        bundle_dir = world["promoted"] / "bundle"
        shutil.rmtree(bundle_dir)
        bundle_dir.symlink_to(twin / "bundle", target_is_directory=True)
        assert load_candidate_bundle(world["promoted"]).candidate_hash == world["bundle"].candidate_hash  # ingestion alone reads through it
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match="bundle directory .* is a symlink"):
            publish_mod.check_traceability(world["bundle"].identity, candidates_dir=world["candidates"])
        assert _snapshot(tmp_path) == before

    def test_a_symlinked_source_record_file_or_directory_is_refused(self, world, no_git, tmp_path: Path) -> None:
        source_dir, _ = publish_mod.find_run_record(world["repo"], world["valid"])
        twin = self._twin(world, tmp_path, source_dir)
        _replace_with_symlink(source_dir / "scores.json", twin / "scores.json")
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match=r"scores\.json is a symlink"):
            publish_mod.find_run_record(world["repo"], world["valid"])
        with pytest.raises(publish_mod.PublicationRefused, match="symlink"):
            _plan(world, [world["valid"]])
        assert _snapshot(tmp_path) == before
        _replace_with_directory_symlink(source_dir, twin)
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match="run record directory .* is a symlink"):
            publish_mod.find_run_record(world["repo"], world["valid"])
        assert _snapshot(tmp_path) == before and not world["dest"].exists()

    def test_a_symlinked_candidate_hash_directory_is_refused_through_every_ancestor(self, world, no_git, tmp_path: Path) -> None:
        """The record is real and valid under the twin tree; only an ancestor
        is a link.  Every component from ``results/`` down is proven, so a
        record reached through a symlinked ancestor is never publishable."""
        source_dir, _ = publish_mod.find_run_record(world["repo"], world["valid"])
        hash_dir = source_dir.parent
        twin = self._twin(world, tmp_path, hash_dir)
        assert publish_mod.read_run_record(twin / world["valid"]).run_id == world["valid"]  # valid on its own
        _replace_with_directory_symlink(hash_dir, twin)
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match="is a symlink") as info:
            publish_mod.find_run_record(world["repo"], world["valid"])
        assert str(hash_dir) in str(info.value) and "refusing to follow" in str(info.value)
        with pytest.raises(publish_mod.PublicationRefused, match="is a symlink"):
            _plan(world, [world["valid"]])
        assert _snapshot(tmp_path) == before and not world["dest"].exists()
        hash_dir.unlink()
        shutil.copytree(twin, hash_dir)
        results_dir = world["repo"] / publish_mod.RESULTS_DIRNAME
        _replace_with_directory_symlink(results_dir, self._twin(world, tmp_path, results_dir))
        before = _snapshot(tmp_path)
        with pytest.raises(publish_mod.PublicationRefused, match="results directory .* is a symlink"):
            _plan(world, [world["valid"]])
        assert _snapshot(tmp_path) == before and not world["dest"].exists()

    def test_a_candidate_hash_directory_swapped_after_planning_is_refused_and_rolled_back(self, world, prior, tmp_path: Path) -> None:
        """Planning proved a real record; before the copy the whole hash
        directory becomes a link to a valid twin.  The proof is repeated
        immediately before the copy, so the transaction refuses, rolls back
        its journal and staging, publishes nothing and leaves the source
        tree, the twin and the pre-existing record untouched."""
        plan = _plan(world, [world["valid"]])
        hash_dir = plan.runs[0].source_dir.parent
        twin = self._twin(world, tmp_path, hash_dir)
        _replace_with_directory_symlink(hash_dir, twin)
        source_before, twin_before = _snapshot(world["repo"]), _snapshot(twin)
        with pytest.raises(publish_mod.PublicationRefused, match="rolled back") as info:
            publish_mod.stage_publication(plan)
        assert "is a symlink" in str(info.value) and "refusing to follow" in str(info.value)
        assert _entries(world["dest"]) == [world["invalid"]]
        assert _tree_with_mtimes(world["dest"] / world["invalid"]) == prior["snapshot"]
        assert _snapshot(world["repo"]) == source_before and _snapshot(twin) == twin_before

    def test_a_source_record_file_replaced_under_the_transaction_is_refused_before_the_copy(self, world, no_git, tmp_path: Path) -> None:
        plan = _plan(world, [world["valid"]])
        source_dir = plan.runs[0].source_dir
        twin = self._twin(world, tmp_path, source_dir)
        _replace_with_symlink(source_dir / "manifest.json", twin / "manifest.json")
        with pytest.raises(publish_mod.PublicationRefused, match=r"manifest\.json is a symlink"):
            publish_mod.stage_publication(plan)
        assert _tree(world["dest"]) == {}

    def test_a_symlinked_destination_record_with_identical_bytes_is_not_already_published(self, world, no_git, tmp_path: Path) -> None:
        publish_mod.stage_publication(_plan(world, [world["valid"]]))
        dest = world["dest"] / world["valid"]
        twin = self._twin(world, tmp_path, dest)
        for name in ("manifest.json", "scores.json"):
            _replace_with_symlink(dest / name, twin / name)
            assert (dest / name).read_bytes() == (twin / name).read_bytes()  # identical through the link
            before = _snapshot(tmp_path)
            plan = _plan(world, [world["valid"]])
            assert plan.runs[0].already_staged is False
            assert any(f"{name} is a symlink" in r and "never overwritten" in r for r in plan.refusals)
            with pytest.raises(publish_mod.PublicationRefused):
                publish_mod.stage_publication(plan)
            assert _snapshot(tmp_path) == before
            (dest / name).unlink()
            shutil.copyfile(twin / name, dest / name)
        _replace_with_directory_symlink(dest, twin)
        before = _snapshot(tmp_path)
        plan = _plan(world, [world["valid"]])
        assert plan.runs[0].already_staged is False
        assert any("record directory" in r and "is a symlink" in r for r in plan.refusals)
        assert _snapshot(tmp_path) == before

    def test_discovery_refuses_symlinked_record_files_and_directories(self, world, no_git, tmp_path: Path) -> None:
        publish_mod.stage_publication(_plan(world, [world["valid"]]))
        root = world["dest"]
        dest = root / world["valid"]
        twin = self._twin(world, tmp_path, dest)
        _replace_with_symlink(dest / "scores.json", twin / "scores.json")
        with pytest.raises(publish_mod.ResultsRepoError, match=r"scores\.json: a symlink"):
            list(publish_mod.iter_published_records(root))
        (dest / "scores.json").unlink()
        shutil.copyfile(twin / "scores.json", dest / "scores.json")
        assert [run_dir.name for run_dir, _ in publish_mod.iter_published_records(root)] == [world["valid"]]
        (root / "linked").symlink_to(twin, target_is_directory=True)
        with pytest.raises(publish_mod.ResultsRepoError, match="linked: a symlink"):
            list(publish_mod.iter_published_records(root))
        (root / "linked").unlink()
        _replace_with_directory(dest / "manifest.json")
        with pytest.raises(publish_mod.ResultsRepoError, match=r"manifest\.json is a directory"):
            list(publish_mod.iter_published_records(root))

    def test_real_candidate_and_record_directories_still_pass(self, world, no_git) -> None:
        plan = _plan(world, [world["valid"], world["valid2"]])
        assert plan.refusals == []
        written = publish_mod.stage_publication(plan)
        assert len(written) == 4
        again = _plan(world, [world["valid"], world["valid2"]])
        assert again.refusals == [] and all(run.already_staged for run in again.runs)
        assert sorted(run_dir.name for run_dir, _ in publish_mod.iter_published_records(world["dest"])) == sorted(
            [world["valid"], world["valid2"]]
        )


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


def _assert_clean(world, prior) -> None:
    """The destination holds exactly the pre-existing record, byte for byte
    and mtime for mtime, and no journal or staging directory."""
    dest = world["dest"]
    assert _entries(dest) == [world["invalid"]], _entries(dest)
    assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
    assert not publish_mod.journal_path(dest).exists()


def _is_the_file_at(fd: int, path: Path) -> bool:
    """Whether *fd* is open on the very file *path* names right now."""
    try:
        here, there = os.fstat(fd), path.stat()
    except OSError:
        return False
    return (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino)


def _cli(world, *run_ids: str, dry_run: bool = False) -> list[str]:
    return [
        "--results-repo", str(world["repo"]), "--dest", str(world["dest"]), "--candidates-dir", str(world["candidates"]),
        "--allow-invalid", *(["--dry-run"] if dry_run else []), *run_ids,
    ]


#: A publication invocation frozen at one phase of its transaction while it
#: holds the destination lock — the live counterpart of the invocation under
#: test.  Run as its own process: the lock arbitrates between processes.
_HOLDER = '''\
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import publish_results as pub  # noqa: E402

args = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
plan = pub.plan_publication(
    args["run_ids"], results_repo=Path(args["repo"]), dest=Path(args["dest"]),
    candidates_dir=Path(args["candidates"]), allow_invalid=True,
)
lock = pub.PublicationLock(plan.dest)
lock.__enter__()
tx = pub.PublicationTransaction(plan)
tx.begin()
phase = args["phase"]
if phase != "begun":
    tx.stage()
if phase == "one-rename":
    tx.commit_one(tx.runs[0])
elif phase == "all-renames":
    tx.commit()
Path(args["ready"]).write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 60
while not Path(args["go"]).exists():
    if time.monotonic() > deadline:
        os._exit(3)
    time.sleep(0.02)
if args["exit"] == "dies":
    os._exit(0)  # dies holding the lock and its journal: the kernel drops the lock
if phase == "begun":
    tx.stage()
if phase in ("begun", "staged"):
    tx.commit()
elif phase == "one-rename":
    tx.commit_one(tx.runs[1])
tx.finish()
lock.__exit__(None, None, None)
'''


class TestSerialization:
    """One invocation per destination.  While a live invocation holds the
    destination — at any phase of its transaction — a second one refuses and
    changes nothing: not the journal, not the staging tree, not a record.
    Once the holder has exited, the next invocation recovers the journal it
    left exactly as documented."""

    PHASES = ("begun", "staged", "one-rename", "all-renames")

    def _hold(self, world, tmp_path: Path, phase: str, *, exit: str) -> tuple[subprocess.Popen, Path]:
        holder = tmp_path / "holder.py"
        holder.write_text(_HOLDER, encoding="utf-8")
        ready, go = tmp_path / "ready", tmp_path / "go"
        args = tmp_path / "holder-args.json"
        args.write_text(json.dumps({
            "run_ids": [world["valid"], world["valid2"]], "repo": str(world["repo"]), "dest": str(world["dest"]),
            "candidates": str(world["candidates"]), "phase": phase, "ready": str(ready), "go": str(go), "exit": exit,
        }), encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(holder), str(REPO_ROOT / "scripts"), str(args)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.monotonic() + 120
        while not ready.exists():
            if proc.poll() is not None or time.monotonic() > deadline:
                proc.kill()
                _out, err = proc.communicate(timeout=10)
                pytest.fail(f"the holder never reached phase {phase}: {err}")
            time.sleep(0.02)
        return proc, go

    def _assert_second_invocation_refuses_without_mutation(self, world, capsys) -> None:
        dest = world["dest"]
        before = _snapshot(dest)
        assert publish_mod.main(_cli(world, world["valid2"])) == 1
        err = capsys.readouterr().err
        assert "REFUSED" in err and "holds" in err and "in flight" in err and "RECOVER" not in err
        assert publish_mod.main(_cli(world, world["valid2"], dry_run=True)) == 1
        err = capsys.readouterr().err
        assert "holds" in err and "changed nothing" in err and "RECOVERY REQUIRED" not in err
        with pytest.raises(publish_mod.PublicationLockedError):
            publish_mod.recover_publication(dest)
        with pytest.raises(publish_mod.PublicationLockedError):
            publish_mod.inspect_publication(dest)
        with pytest.raises(publish_mod.PublicationLockedError), publish_mod.PublicationLock(dest):
            pass  # pragma: no cover - the lock is never taken
        assert _snapshot(dest) == before, "the second invocation changed the holder's tree"

    @pytest.mark.parametrize("phase", PHASES)
    def test_a_second_invocation_refuses_at_every_phase_and_the_next_recovers_the_stale_journal(
        self, world, prior, tmp_path: Path, capsys, phase: str
    ) -> None:
        dest = world["dest"]
        proc, go = self._hold(world, tmp_path, phase, exit="dies")
        try:
            self._assert_second_invocation_refuses_without_mutation(world, capsys)
        finally:
            go.write_text("go", encoding="utf-8")
            proc.wait(timeout=120)
        assert proc.returncode == 0, proc.stderr.read()
        assert publish_mod.journal_path(dest).exists(), "the holder died with its journal in place"
        # Its lock died with it: the next invocation recovers first, then publishes.
        code = publish_mod.main(_cli(world, world["valid"], world["valid2"]))
        out = capsys.readouterr().out
        assert code == 0 and out.startswith("RECOVERED"), out
        if phase == "all-renames":
            assert "already committed every record" in out and "nothing to publish" in out
        else:
            assert "rolling it back" in out and "approval stamp" in out
        assert _entries(dest) == sorted([world["invalid"], world["valid"], world["valid2"]])
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        assert not publish_mod.journal_path(dest).exists()

    def test_a_holder_that_finishes_leaves_the_next_invocation_nothing_to_recover(self, world, prior, tmp_path: Path, capsys) -> None:
        dest = world["dest"]
        proc, go = self._hold(world, tmp_path, "staged", exit="finishes")
        try:
            self._assert_second_invocation_refuses_without_mutation(world, capsys)
        finally:
            go.write_text("go", encoding="utf-8")
            proc.wait(timeout=120)
        assert proc.returncode == 0, proc.stderr.read()
        assert _entries(dest) == sorted([world["invalid"], world["valid"], world["valid2"]])
        code = publish_mod.main(_cli(world, world["valid"], world["valid2"]))
        out = capsys.readouterr().out
        assert code == 0 and not out.startswith("RECOVERED") and "nothing to publish" in out
        assert out.count("— already published (identical)") == 2

    def test_the_cli_in_another_process_is_refused_while_this_process_holds_the_destination(self, world, prior, capsys) -> None:
        dest = world["dest"]
        script = REPO_ROOT / "scripts" / "publish_results.py"
        before = _snapshot(dest)
        with publish_mod.PublicationLock(dest):
            for extra in ([], ["--dry-run"]):
                proc = subprocess.run(
                    [sys.executable, str(script), *_cli(world, world["valid"]), *extra],
                    capture_output=True, text=True, timeout=120, check=False,
                )
                assert proc.returncode == 1, proc.stderr
                assert "REFUSED" in proc.stderr and "holds" in proc.stderr and "in flight" in proc.stderr
                assert "Traceback" not in proc.stderr
            assert _snapshot(dest) == before
        # Released: the same command publishes.
        assert publish_mod.main(_cli(world, world["valid"])) == 0
        assert _entries(dest) == sorted([world["invalid"], world["valid"]])

    def test_the_lock_re_enters_within_one_process_and_leaves_no_artifact(self, world, prior) -> None:
        dest = world["dest"]
        before = _snapshot(dest)
        with publish_mod.PublicationLock(dest) as outer:
            with publish_mod.PublicationLock(dest) as inner, publish_mod.PublicationLock(dest, shared=True) as probe:
                assert outer.held and inner.held and probe.held
                assert publish_mod.recover_publication(dest) is None and publish_mod.inspect_publication(dest) is None
            assert outer.held
        assert not outer.held
        assert _snapshot(dest) == before, "locking wrote or touched nothing under the destination"
        assert not any(name.startswith(".") for name in _entries(dest))

    def test_an_absent_destination_is_created_for_the_lifecycle_and_removed_when_nothing_was_published(self, world, no_git, capsys) -> None:
        dest = world["dest"]
        assert not dest.exists()
        with publish_mod.PublicationLock(dest, shared=True) as probe:
            assert not probe.held and not dest.exists(), "a shared hold never creates the destination"
        assert publish_mod.main(_cli(world, world["untraceable"])) == 1
        assert not dest.exists(), "a refused plan leaves no empty destination behind"
        assert publish_mod.main(_cli(world, world["valid"])) == 0
        assert _entries(dest) == [world["valid"]]


class TestCreatedDestination:
    """An exclusive hold creates an absent destination for the lifecycle and,
    when the invocation published nothing, removes it on release — only if
    the path still names that very directory and it is empty.  Anything else
    is kept, and kept loudly: never a clean refusal over residue, never the
    removal of what another party put there."""

    def _deny_removing(self, monkeypatch: pytest.MonkeyPatch, directory: Path):
        """``os.rmdir`` is denied for *directory*; returns the real ``rmdir``
        so a test can clear the retained directory between invocations."""
        real = os.rmdir

        def denied(path, *a, **kw):
            if Path(path) == directory:
                raise PermissionError(errno.EACCES, "Permission denied")
            return real(path, *a, **kw)

        monkeypatch.setattr(os, "rmdir", denied)
        return real

    def test_a_permission_failure_removing_the_created_destination_is_loud_and_keeps_the_refusal(
        self, world, no_git, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        assert not dest.exists()
        rmdir = self._deny_removing(monkeypatch, dest)
        refusal = publish_mod.PublicationRefused("nothing traceable")
        with pytest.raises(publish_mod.PublicationCleanupError) as info, publish_mod.PublicationLock(dest):
            assert dest.is_dir()
            raise refusal
        exc = info.value
        assert exc.path == dest and exc.refusal is refusal, "the refusal in flight is attached"
        assert isinstance(exc.__cause__, PermissionError) and f"rmdir {dest}" in str(exc)
        assert exc.__context__ is exc.__cause__ and exc.__context__.__context__ is refusal, "the chain runs cleanup failure → refusal"
        assert dest.is_dir() and _entries(dest) == []
        rmdir(dest)
        # The CLI cannot report a refused plan as clean while the directory it created stays behind.
        code = publish_mod.main(_cli(world, world["untraceable"]))
        out, err = capsys.readouterr()
        assert code == 2 and "REFUSED" in out and "CLEANUP FAILED" in err and str(dest) in err and "Traceback" not in out + err
        assert dest.is_dir() and _entries(dest) == []
        monkeypatch.undo()
        assert publish_mod.main(_cli(world, world["untraceable"])) == 1
        assert dest.is_dir(), "a directory that pre-exists an invocation is never its to remove — the retained one is removed by hand"
        rmdir(dest)
        assert publish_mod.main(_cli(world, world["untraceable"])) == 1
        assert not dest.exists()

    def test_a_replaced_destination_is_never_removed(self, world, no_git, tmp_path: Path) -> None:
        dest = world["dest"]
        moved = tmp_path / "moved-away"
        with pytest.raises(publish_mod.PublicationCleanupError, match="no longer names") as info, publish_mod.PublicationLock(dest):
            os.rename(dest, moved)
            dest.mkdir()
            (dest / "theirs.txt").write_text("not ours\n", encoding="utf-8")
        assert info.value.path == dest and info.value.refusal is None
        assert moved.is_dir() and _entries(moved) == [], "the directory this invocation created stays where it went"
        assert (dest / "theirs.txt").read_text(encoding="utf-8") == "not ours\n", "the replacement is untouched"

    def test_a_destination_that_became_non_empty_is_kept_and_reported(self, world, no_git) -> None:
        dest = world["dest"]
        with pytest.raises(publish_mod.PublicationCleanupError, match="not empty") as info, publish_mod.PublicationLock(dest):
            (dest / "theirs.txt").write_text("not ours\n", encoding="utf-8")
        assert info.value.path == dest and isinstance(info.value.__cause__, OSError) and "kept" in str(info.value)
        assert _entries(dest) == ["theirs.txt"] and (dest / "theirs.txt").read_text(encoding="utf-8") == "not ours\n"

    def test_a_rolled_back_publication_leaves_no_created_destination(self, world, no_git, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        dest = world["dest"]
        real = os.rename

        def refuse(src, dst, *a, **kw):
            if Path(dst).parent == dest:
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            return real(src, dst, *a, **kw)

        monkeypatch.setattr(os, "rename", refuse)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 1 and "rolled back" in err and "Traceback" not in out + err
        assert not dest.exists(), "rolled back to empty, the created destination goes too"

    def test_a_recovery_error_keeps_the_created_destination_as_the_home_of_its_evidence(
        self, world, no_git, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)
        real_mkdir, real_unlink = os.mkdir, os.unlink

        def denied_mkdir(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                raise PermissionError(13, "Permission denied")
            return real_mkdir(path, *a, **kw)

        def denied_unlink(path, *a, **kw):
            if Path(path) == journal:
                raise PermissionError(1, "Operation not permitted")
            return real_unlink(path, *a, **kw)

        monkeypatch.setattr(os, "mkdir", denied_mkdir)
        monkeypatch.setattr(os, "unlink", denied_unlink)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 2 and "RECOVERY FAILED" in err and "KEPT" in err and "CLEANUP FAILED" not in err and "Traceback" not in out + err
        assert _entries(dest) == [publish_mod.JOURNAL_FILENAME], "the kept journal needs its directory"
        monkeypatch.undo()
        code = publish_mod.main(_cli(world, world["valid"]))
        assert code == 0 and capsys.readouterr().out.startswith("RECOVERED") and _entries(dest) == [world["valid"]]


class TestBegin:
    """Initialization is all-or-nothing.  A failure while creating, writing
    or closing the journal, or while creating staging, leaves nothing behind
    and refuses with the cause chained; a cleanup that itself fails keeps the
    evidence, names it, says what to do, and still chains the original
    failure — and the CLI never prints a raw traceback for any of it."""

    def _refuses_cleanly(self, world, prior, capsys, *, match: str) -> None:
        with pytest.raises(publish_mod.PublicationRefused, match=match) as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert isinstance(info.value.__cause__, OSError), "the original failure is chained"
        _assert_clean(world, prior)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 1 and "REFUSED" in err and "Traceback" not in out + err
        _assert_clean(world, prior)

    def test_a_journal_that_cannot_be_created_refuses_with_nothing_created(self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        real_open = os.open

        def denied(path, flags, *a, **kw):
            if Path(path).name == publish_mod.JOURNAL_FILENAME and flags & os.O_CREAT:
                raise PermissionError(13, "Permission denied")
            return real_open(path, flags, *a, **kw)

        monkeypatch.setattr(os, "open", denied)
        self._refuses_cleanly(world, prior, capsys, match="could not be created")

    @pytest.mark.parametrize("failing_step", ["write", "close"])
    def test_a_journal_write_or_close_failure_removes_the_half_made_journal(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys, failing_step: str
    ) -> None:
        real = publish_mod._write_whole

        def failing(fd, data):
            if failing_step == "write":
                os.write(fd, data[: len(data) // 2])  # half a journal lands on disk
                os.close(fd)
                raise OSError(28, "No space left on device")
            real(fd, data)  # the whole journal lands, then the close fails
            raise OSError(5, "Input/output error")

        monkeypatch.setattr(publish_mod, "_write_whole", failing)
        self._refuses_cleanly(world, prior, capsys, match="cannot begin")

    def test_a_staging_mkdir_failure_removes_the_journal(self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        real = os.mkdir

        def denied(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                raise PermissionError(13, "Permission denied")
            return real(path, *a, **kw)

        monkeypatch.setattr(os, "mkdir", denied)
        self._refuses_cleanly(world, prior, capsys, match="cannot begin")

    def test_a_cleanup_failure_keeps_a_complete_journal_as_evidence_and_says_what_to_do(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)
        real_mkdir, real_unlink = os.mkdir, os.unlink

        def denied_mkdir(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                raise PermissionError(13, "Permission denied")
            return real_mkdir(path, *a, **kw)

        def denied_unlink(path, *a, **kw):
            if Path(path) == journal:
                raise PermissionError(1, "Operation not permitted")
            return real_unlink(path, *a, **kw)

        monkeypatch.setattr(os, "mkdir", denied_mkdir)
        monkeypatch.setattr(os, "unlink", denied_unlink)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="KEPT") as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        message = str(info.value)
        assert str(journal) in message and world["valid"] in message and "delete it by hand" in message
        assert isinstance(info.value.__cause__, PermissionError) and info.value.__cause__.errno == 13, "the original failure is the cause"
        assert isinstance(info.value.__context__, PermissionError) and info.value.__context__.errno == 1, "the cleanup failure is the context"
        assert _entries(dest) == sorted([world["invalid"], publish_mod.JOURNAL_FILENAME]), "the journal is the only residue"
        parsed = publish_mod.Journal.from_dict(json.loads(journal.read_text(encoding="utf-8")))
        assert parsed.planned == [world["valid"]] and parsed.committed == [] and parsed.committing is None
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 2 and "RECOVERY FAILED" in err and "is kept" in err and "Traceback" not in out + err
        # The permission problem fixed, the retained journal is ordinary recovery.
        monkeypatch.undo()
        code = publish_mod.main(_cli(world, world["valid"]))
        out = capsys.readouterr().out
        assert code == 0 and out.startswith("RECOVERED") and "removed no record directory" in out
        assert _entries(dest) == sorted([world["invalid"], world["valid"]]) and not journal.exists()

    def test_a_cleanup_failure_after_a_partial_write_names_the_unparsable_journal(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)
        real_unlink = os.unlink

        def half_then_fail(fd, data):
            os.write(fd, data[: len(data) // 2])
            os.close(fd)
            raise OSError(28, "No space left on device")

        def denied_unlink(path, *a, **kw):
            if Path(path) == journal:
                raise PermissionError(1, "Operation not permitted")
            return real_unlink(path, *a, **kw)

        monkeypatch.setattr(publish_mod, "_write_whole", half_then_fail)
        monkeypatch.setattr(os, "unlink", denied_unlink)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="does not parse") as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert isinstance(info.value.__cause__, OSError) and info.value.__cause__.errno == 28
        assert journal.exists() and not any(name.startswith(publish_mod.STAGING_PREFIX) for name in _entries(dest))
        monkeypatch.undo()
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 2 and "RECOVERY FAILED" in err and "cannot read" in err and "Traceback" not in out + err
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]
        journal.unlink()  # what the instructions say, once inspected
        assert publish_mod.main(_cli(world, world["valid"])) == 0
        assert _entries(dest) == sorted([world["invalid"], world["valid"]])

    def _deny_duplicating_the_journal_descriptor(self, world, monkeypatch: pytest.MonkeyPatch) -> None:
        """``os.dup`` fails — the process is out of descriptors — exactly on
        the journal's own descriptor, the moment after the journal was created."""
        journal = publish_mod.journal_path(world["dest"])
        real_dup = os.dup

        def exhausted(fd):
            if _is_the_file_at(fd, journal):
                raise OSError(errno.EMFILE, "Too many open files")
            return real_dup(fd)

        monkeypatch.setattr(os, "dup", exhausted)

    def test_a_descriptor_duplication_failure_leaves_no_empty_journal_and_no_traceback(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        journal = publish_mod.journal_path(world["dest"])
        self._deny_duplicating_the_journal_descriptor(world, monkeypatch)
        failure: BaseException | None = None
        try:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        except BaseException as exc:  # noqa: BLE001 - whatever escapes is the evidence
            failure = exc
        residue = journal.read_bytes() if journal.exists() else None
        assert isinstance(failure, publish_mod.PublicationRefused), (
            f"{type(failure).__name__} escaped raw and the journal holds {residue!r}"
        )
        assert residue is None, f"an empty journal is left behind: {residue!r}"
        assert "cannot begin" in str(failure)
        assert isinstance(failure.__cause__, OSError) and failure.__cause__.errno == errno.EMFILE, "the original failure is the cause"
        _assert_clean(world, prior)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 1 and "REFUSED" in err and "Too many open files" in err and "Traceback" not in out + err
        _assert_clean(world, prior)

    def test_a_failed_beginning_leaves_no_destination_this_invocation_created(
        self, world, no_git, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        assert not dest.exists()
        self._deny_duplicating_the_journal_descriptor(world, monkeypatch)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 1 and "REFUSED" in err and "cannot begin" in err and "Traceback" not in out + err
        assert not dest.exists(), "the empty destination created for a publication that never began is gone"
        monkeypatch.undo()
        assert publish_mod.main(_cli(world, world["valid"])) == 0
        assert _entries(dest) == [world["valid"]]

    def _fail_closing_the_proof_descriptor(self, world, monkeypatch: pytest.MonkeyPatch, *, then=None) -> None:
        """Closing the duplicate of the journal's descriptor reports an I/O
        error — after the descriptor is released, as the kernel does — and
        *then* runs, if given, before the error is raised."""
        journal = publish_mod.journal_path(world["dest"])
        real_dup, real_close = os.dup, os.close
        proofs: set[int] = set()

        def dup(fd):
            new = real_dup(fd)
            if _is_the_file_at(fd, journal):
                proofs.add(new)
            return new

        def close(fd):
            real_close(fd)
            if fd in proofs:
                proofs.discard(fd)
                if then is not None:
                    then()
                raise OSError(errno.EIO, "Input/output error")

        monkeypatch.setattr(os, "dup", dup)
        monkeypatch.setattr(os, "close", close)

    def test_a_failure_closing_the_last_descriptor_removes_staging_and_the_journal_it_reads_back(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._fail_closing_the_proof_descriptor(world, monkeypatch)
        with pytest.raises(publish_mod.PublicationRefused, match="cannot begin") as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert isinstance(info.value.__cause__, OSError) and info.value.__cause__.errno == errno.EIO
        _assert_clean(world, prior)
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 1 and "REFUSED" in err and "Input/output error" in err and "Traceback" not in out + err
        _assert_clean(world, prior)

    def test_without_an_open_descriptor_a_journal_with_other_content_is_not_removed(
        self, world, prior, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No descriptor of the created file is open any more, so its link
        count cannot settle identity; the entry must read back as exactly
        what this attempt wrote.  Whether or not the filesystem reuses the
        freed inode, an impostor with other content stays."""
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)

        def replace_the_journal() -> None:
            journal.unlink()
            journal.write_text("{}\n", encoding="utf-8")

        self._fail_closing_the_proof_descriptor(world, monkeypatch, then=replace_the_journal)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="no longer the file this transaction created") as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert isinstance(info.value.__cause__, OSError) and info.value.__cause__.errno == errno.EIO
        assert journal.read_text(encoding="utf-8") == "{}\n", "the impostor is kept for inspection, never removed"
        assert not any(name.startswith(publish_mod.STAGING_PREFIX) for name in _entries(dest)), "this attempt's staging is gone"
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]

    def test_a_staging_removal_failure_while_abandoning_keeps_both_and_the_next_invocation_recovers(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)
        real_rmdir = os.rmdir

        def busy(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                raise OSError(errno.EBUSY, "Device or resource busy")
            return real_rmdir(path, *a, **kw)

        self._fail_closing_the_proof_descriptor(world, monkeypatch)
        monkeypatch.setattr(os, "rmdir", busy)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="staging directory it had created could not be removed") as info:
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        message = str(info.value)
        assert "KEPT" in message and str(journal) in message and world["valid"] in message
        assert isinstance(info.value.__cause__, OSError) and info.value.__cause__.errno == errno.EIO, "the original failure is the cause"
        assert isinstance(info.value.__context__, OSError) and info.value.__context__.errno == errno.EBUSY, "the cleanup failure is the context"
        parsed = publish_mod.Journal.from_dict(json.loads(journal.read_text(encoding="utf-8")))
        staging = dest / parsed.staging
        assert parsed.planned == [world["valid"]] and parsed.committed == [] and staging.is_dir() and _entries(staging) == []
        assert _entries(dest) == sorted([world["invalid"], publish_mod.JOURNAL_FILENAME, parsed.staging]), "journal and staging are the only residue"
        # As the instructions say: the journal parses, so the next invocation recovers it.
        monkeypatch.undo()
        code = publish_mod.main(_cli(world, world["valid"]))
        out = capsys.readouterr().out
        assert code == 0 and out.startswith("RECOVERED") and "removed no record directory" in out
        assert _entries(dest) == sorted([world["invalid"], world["valid"]]) and not journal.exists()

    def test_a_journal_replaced_before_cleanup_is_not_removed(self, world, prior, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = world["dest"]
        journal = publish_mod.journal_path(dest)
        real = os.mkdir

        def swap_then_fail(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                journal.unlink()
                journal.write_text("{}\n", encoding="utf-8")  # someone else's file under the journal's name
                raise PermissionError(13, "Permission denied")
            return real(path, *a, **kw)

        monkeypatch.setattr(os, "mkdir", swap_then_fail)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="no longer the file this transaction created"):
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert journal.read_text(encoding="utf-8") == "{}\n", "the impostor is kept for inspection, never removed"
        assert _tree_with_mtimes(dest / world["invalid"]) == prior["snapshot"]

    def test_a_finish_failure_after_every_commit_keeps_a_complete_journal_the_next_invocation_finishes(
        self, world, prior, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        dest = world["dest"]
        real = shutil.rmtree

        def busy(path, *a, **kw):
            if Path(path).name.startswith(publish_mod.STAGING_PREFIX):
                raise OSError(16, "Device or resource busy")
            return real(path, *a, **kw)

        monkeypatch.setattr(shutil, "rmtree", busy)
        with pytest.raises(publish_mod.PublicationRecoveryError, match="every record was committed"):
            publish_mod.stage_publication(_plan(world, [world["valid"]]))
        assert (dest / world["valid"] / "manifest.json").is_file()
        assert publish_mod.Journal.from_dict(json.loads(publish_mod.journal_path(dest).read_text(encoding="utf-8"))).complete
        code = publish_mod.main(_cli(world, world["valid"]))
        out, err = capsys.readouterr()
        assert code == 2 and "RECOVERY FAILED" in err and "Traceback" not in out + err
        monkeypatch.undo()
        code = publish_mod.main(_cli(world, world["valid"]))
        out = capsys.readouterr().out
        assert code == 0 and out.startswith("RECOVERED") and "already committed every record" in out and "nothing to publish" in out
        assert _entries(dest) == sorted([world["invalid"], world["valid"]]) and not publish_mod.journal_path(dest).exists()
