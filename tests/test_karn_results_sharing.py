"""Workspace archives, provenance and exclusions that let hosts share one results repo."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn import execution, provenance
from silverquillm.karn.exclusions import (
    ExclusionError,
    check,
    exclude,
    load_exclusions,
    rule_exclusion,
)
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.records import KarnRunRecord, read_record, write_record
from silverquillm.karn.regrade import regrade
from silverquillm.karn.workspace_archive import (
    ArchiveRefused,
    Scratch,
    archive_dir,
    archive_run,
    backfill,
    content_digest,
    materialize,
)
from silverquillm.results_repo import InvalidRunRecordError

from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker
from .retained_runs import building, clone_tree, rebase_options
from .test_karn_execution import FixtureHost, options


class EditingHost(FixtureHost):
    """A run whose agent edits, adds, deletes, and writes binary and CRLF files."""

    def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
        (workspace / "engine/card.py").write_text("value = 1  # edited\n")
        (workspace / "docs/readme.txt").unlink()
        (workspace / "cards/fdn/fdn_1/art.bin").write_bytes(bytes(range(256)) * 4)
        (workspace / "cards/fdn/fdn_1/notes.txt").write_bytes(b"line one\r\nline two\r\n")
        (workspace / ".gitattributes").write_text("* text eol=lf\n")
        script = workspace / "tool.sh"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        return super().run(candidate, workspace, evidence_dir, prompt, **kwargs)


def tree_bytes(root: Path, *, graded_only: bool = False) -> dict:
    """Every file's hash; ``graded_only`` drops the bytecode the local grader leaves behind."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not (graded_only and "__pycache__" in path.parts)
    }


@pytest.fixture(scope="module")
def edited_template(tmp_path_factory):
    """A run whose agent edited its workspace, built once; read it, never change it."""
    root = tmp_path_factory.mktemp("edited")
    opts = options(root, host=EditingHost())
    readme = opts["bench_root"] / "benchmarks/example/workspace/docs/readme.txt"
    readme.parent.mkdir()
    readme.write_text("deleted by the agent\n")
    with building():
        record = run_benchmark(**opts, run_id="edited")
    yield SimpleNamespace(root=root, opts=opts, record=record)
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def edited(edited_template, tmp_path):
    """A clone of the edited run in this test's ``tmp_path``, with its record read from there."""
    clone_tree(edited_template.root, tmp_path)
    opts = rebase_options(edited_template.opts, edited_template.root, tmp_path)
    record = edited_template.record
    return opts, read_record(opts["results_repo"] / "results" / record.candidate.hash / "edited")


# ---- workspace archives ----------------------------------------------------------------------


def test_a_run_archives_its_graded_workspace_and_it_rebuilds_byte_for_byte(edited, tmp_path):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    archive = archive_dir(repo, record.candidate.hash, record.run_id)
    metadata = json.loads((archive / "workspace.json").read_text())
    assert metadata["graded"]["source"] == "workspace_final"
    assert (
        metadata["graded"]["content_digest"]
        == record.run_metadata["grading_source"]["final"]["digest"]
    )
    assert (
        metadata["baseline"]["content_digest"]
        == record.run_metadata["benchmark_input"]["workspace_digest"]
    )
    assert (repo / metadata["baseline"]["bundle"]).is_file()
    assert metadata["patch"]["files_changed"] == 6

    rebuilt = materialize(repo, record, tmp_path / "rebuilt")

    assert tree_bytes(rebuilt) == tree_bytes(run_dir / "workspace_final", graded_only=True)
    assert os.access(rebuilt / "tool.sh", os.X_OK)
    assert not (rebuilt / "docs/readme.txt").exists()


def test_runs_of_one_benchmark_input_share_one_baseline(edited):
    opts, _ = edited
    run_benchmark(**opts, run_id="second")
    assert len(list((opts["results_repo"] / "baselines").iterdir())) == 1
    assert len(list((opts["results_repo"] / "workspaces").glob("*/*"))) == 2


def test_the_scratch_repository_ignores_attributes_and_filters(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".gitattributes").write_text("* text eol=crlf filter=missing\n")
    (source / "text.txt").write_bytes(b"a\nb\r\n")
    scratch = Scratch(tmp_path / "scratch")
    tree = scratch.tree(source)
    scratch.write_tree(tree, tmp_path / "out")
    assert (tmp_path / "out/text.txt").read_bytes() == b"a\nb\r\n"
    assert content_digest(tmp_path / "out") == content_digest(source)


def test_archiving_never_writes_into_the_run_artifacts(edited):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    before = tree_bytes(run_dir)

    assert archive_run(repo, record, run_dir)["status"] == "archived"

    assert tree_bytes(run_dir) == before


def test_an_existing_archive_is_kept_and_a_dry_run_writes_nothing(edited):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    archive = archive_dir(repo, record.candidate.hash, record.run_id)
    assert archive_run(repo, record, run_dir)["status"] == "exists"
    shutil.rmtree(archive)
    assert archive_run(repo, record, run_dir, dry_run=True)["status"] == "would_archive"
    assert not archive.exists()


def test_a_changed_graded_copy_is_refused(edited):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    (run_dir / "workspace_final/engine/card.py").write_text("value = 2\n")
    with pytest.raises(ArchiveRefused, match="graded_workspace_changed"):
        archive_run(repo, record, run_dir)


def test_a_baseline_bundle_is_written_once_and_a_corrupt_one_is_never_replaced(edited):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    [bundle] = (repo / "baselines").iterdir()
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    bundle.write_bytes(b"not a bundle")
    with pytest.raises(ArchiveRefused):
        archive_run(repo, record, run_dir)
    assert bundle.read_bytes() == b"not a bundle"
    assert not archive_dir(repo, record.candidate.hash, record.run_id).exists()


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        (lambda m, a: m["graded"].update(tree="f" * 40), "workspace_tree_mismatch"),
        (lambda m, a: (a / "workspace.patch").write_bytes(b"x"), "workspace_patch_digest_mismatch"),
        (lambda m, a: m["graded"].update(content_digest="sha256:" + "0" * 64), "does_not_match"),
    ],
)
def test_a_rebuild_that_differs_from_the_record_is_refused(edited, tmp_path, tamper, reason):
    opts, record = edited
    archive = archive_dir(opts["results_repo"], record.candidate.hash, record.run_id)
    metadata = json.loads((archive / "workspace.json").read_text())
    tamper(metadata, archive)
    (archive / "workspace.json").write_text(json.dumps(metadata))
    with pytest.raises(ArchiveRefused, match=reason):
        materialize(opts["results_repo"], record, tmp_path / "rebuilt")


def test_backfill_archives_local_runs_and_skips_other_hosts_runs(edited, tmp_path):
    opts, record = edited
    repo = opts["results_repo"]
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    other = run_benchmark(**opts, run_id="elsewhere")
    shutil.rmtree(opts["results_dir"] / "elsewhere")
    shutil.rmtree(archive_dir(repo, other.candidate.hash, other.run_id))

    rows = {row["run_id"]: row for row in backfill(repo, opts["results_dir"])}

    assert rows["edited"]["status"] == "archived"
    assert rows["elsewhere"] == {
        "run_id": "elsewhere",
        "candidate_hash": other.candidate.hash,
        "status": "skipped",
        "reason": "run_artifacts_unavailable",
    }
    assert backfill(repo, opts["results_dir"], runs=["edited"])[0]["status"] == "exists"


def test_the_archive_command_reports_refusals_and_exits_non_zero(edited):
    opts, record = edited
    repo, run_dir = opts["results_repo"], opts["results_dir"] / "edited"
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    (run_dir / "workspace_final/engine/card.py").write_text("value = 2\n")
    result = CliRunner().invoke(
        main,
        [
            "results",
            "archive",
            "--results-repo",
            str(repo),
            "--results-dir",
            str(opts["results_dir"]),
        ],
    )
    assert result.exit_code == 1
    assert "refused edited: graded_workspace_changed" in result.output


# ---- regrade from another host's archive ------------------------------------------------------


class OtherHostDocker(LocalDocker):
    """This host lacks the recorded grader image but has its own grader for the same Python."""

    LOCAL = "sha256:" + "1" * 64

    def image_id(self, reference):
        return None if reference == FIXTURE_IMAGE_ID else self.LOCAL

    def image_python(self, image_id):
        return "3.13"


def test_another_hosts_run_regrades_from_its_archive_on_a_substituted_grader(edited, tmp_path):
    opts, record = edited
    shutil.rmtree(opts["results_dir"] / "edited")
    common = {
        "bench_root": opts["bench_root"],
        "benchmark_id": "example",
        "results_repo": opts["results_repo"],
        "results_dir": opts["results_dir"],
        "out": tmp_path / "regrade",
        "docker": OtherHostDocker(),
    }

    assert regrade(**common)["skipped"] == [
        {"run_id": "edited", "reason": "grader_image_unavailable"}
    ]
    regrade(**common, substitute_grader=True)

    result = json.loads(next((tmp_path / "regrade").glob("*/edited.json")).read_text())
    assert result["scores"] == record.scores
    assert result["source"]["workspace"] == "results_repo"
    assert result["grading_isolation"]["grader_image_id"] == OtherHostDocker.LOCAL
    assert result["grader_substituted_for"] == FIXTURE_IMAGE_ID


def _another_host(edited, tmp_path, docker):
    opts, _ = edited
    shutil.rmtree(opts["results_dir"] / "edited", ignore_errors=True)
    return {
        "bench_root": opts["bench_root"],
        "benchmark_id": "example",
        "results_repo": opts["results_repo"],
        "results_dir": opts["results_dir"],
        "out": tmp_path / "regrade",
        "docker": docker,
    }


def _output(tmp_path):
    return next((tmp_path / "regrade").glob("*/edited.json"))


def test_a_substituted_output_is_reused_only_under_the_same_substitution(edited, tmp_path):
    regrade(**_another_host(edited, tmp_path, OtherHostDocker()), substitute_grader=True)

    again = OtherHostDocker()
    assert (
        regrade(**_another_host(edited, tmp_path, again), substitute_grader=True)["skipped"] == []
    )
    assert again.runs == []

    plain = regrade(**_another_host(edited, tmp_path, OtherHostDocker()))
    assert plain["skipped"] == [{"run_id": "edited", "reason": "grader_image_unavailable"}]

    path = _output(tmp_path)
    value = json.loads(path.read_text())
    value["grader_substituted_for"] = "sha256:" + "2" * 64
    path.write_text(json.dumps(value))
    repaired = OtherHostDocker()
    regrade(**_another_host(edited, tmp_path, repaired), substitute_grader=True)
    assert len(repaired.runs) == 1
    assert json.loads(path.read_text())["grader_substituted_for"] == FIXTURE_IMAGE_ID


def test_an_output_on_the_recorded_grader_is_not_reused_when_this_host_substitutes(
    edited, tmp_path
):
    regrade(**_another_host(edited, tmp_path, LocalDocker()))
    assert "grader_substituted_for" not in json.loads(_output(tmp_path).read_text())

    substituting = OtherHostDocker()
    regrade(**_another_host(edited, tmp_path, substituting), substitute_grader=True)

    assert len(substituting.runs) == 1
    result = json.loads(_output(tmp_path).read_text())
    assert result["grading_isolation"]["grader_image_id"] == OtherHostDocker.LOCAL
    assert result["grader_substituted_for"] == FIXTURE_IMAGE_ID


@pytest.mark.parametrize("workspace", [[], {}, 7])
def test_a_cached_workspace_source_of_the_wrong_type_is_a_miss(edited, tmp_path, workspace):
    regrade(**_another_host(edited, tmp_path, LocalDocker()))
    path = _output(tmp_path)
    value = json.loads(path.read_text())
    value["source"]["workspace"] = workspace
    path.write_text(json.dumps(value))
    docker = LocalDocker()

    summary = regrade(**_another_host(edited, tmp_path, docker))

    assert len(docker.runs) == 1 and summary["errors"] == []
    assert json.loads(path.read_text())["source"]["workspace"] == "results_repo"


# ---- provenance and the clean-source rule ------------------------------------------------------


def git(root: Path, *arguments):
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "silverquillm").mkdir(parents=True)
    (root / "silverquillm/module.py").write_text("x = 1\n")
    (root / "notes.md").write_text("tracked\n")
    git(root, "init", "--quiet")
    git(root, "add", "--all")
    git(root, "commit", "--quiet", "-m", "initial")
    return root


def test_a_committed_checkout_is_clean(checkout):
    state = provenance.checkout_state(checkout / "silverquillm")
    assert state["dirty"] is False and len(state["commit"]) == 40


@pytest.mark.parametrize(
    ("change", "dirty"),
    [
        (lambda root: (root / "notes.md").write_text("edited\n"), True),
        (lambda root: (root / "silverquillm/new.py").write_text(""), True),
        (lambda root: (root / "benchmarks/x/data.json").parent.mkdir(parents=True)
         or (root / "benchmarks/x/data.json").write_text("{}"), True),
        (lambda root: (root / "scratch-notes.md").write_text("untracked elsewhere\n"), False),
    ],
)  # fmt: skip
def test_tracked_changes_and_untracked_code_or_data_make_a_checkout_dirty(checkout, change, dirty):
    change(checkout)
    assert provenance.checkout_state(checkout)["dirty"] is dirty


def test_a_directory_outside_git_has_no_commit(tmp_path):
    assert provenance.checkout_state(tmp_path) == {"commit": None, "dirty": None}


def test_dirty_sources_are_refused_and_an_override_is_recorded(checkout, monkeypatch):
    monkeypatch.setattr(provenance, "PACKAGE", checkout / "silverquillm")
    monkeypatch.setenv(provenance.HOST_LABEL_ENV, "bench-host-1")
    clean = {provenance.RECIPE_LABEL: "a" * 40}
    recorded = provenance.collect(clean, checkout, allow_dirty=False)
    assert recorded["host_label"] == "bench-host-1" and recorded["dirty_reasons"] == []
    assert provenance.valid(recorded)

    with pytest.raises(provenance.DirtySourceError, match="recipe_revision_dirty"):
        provenance.collect({provenance.RECIPE_LABEL: "dirty"}, checkout, allow_dirty=False)
    with pytest.raises(provenance.DirtySourceError, match="recipe_revision_unrecorded"):
        provenance.collect({}, checkout, allow_dirty=False)
    (checkout / "notes.md").write_text("edited\n")
    with pytest.raises(provenance.DirtySourceError, match="bench_checkout_dirty"):
        provenance.collect(clean, checkout, allow_dirty=False)

    overridden = provenance.collect(clean, checkout, allow_dirty=True)
    assert overridden["allow_dirty"] is True
    assert overridden["dirty_reasons"] == ["bench_checkout_dirty", "benchmark_root_dirty"]
    assert provenance.valid(overridden)
    assert not provenance.valid({**overridden, "allow_dirty": False})


def test_a_dirty_run_is_refused_before_any_evidence_exists(tmp_path, checkout, monkeypatch):
    monkeypatch.setattr(execution, "collect_provenance", provenance.collect)
    monkeypatch.setattr(provenance, "PACKAGE", checkout / "silverquillm")
    opts = options(tmp_path)
    with pytest.raises(provenance.DirtySourceError, match="recipe_revision_unrecorded"):
        run_benchmark(**opts, run_id="refused")
    assert not (opts["results_dir"] / "refused").exists()
    assert not opts["results_repo"].exists()


# ---- the imported package must be the bench root's own -----------------------------------------

#: The real rule; unit tests lift it so toy benchmarks can grade from temporary bench roots.
REQUIRE_PACKAGE_FROM = provenance.require_package_from
REPO = Path(provenance.__file__).resolve().parents[2]


def test_a_package_from_another_checkout_is_refused(checkout, tmp_path, monkeypatch):
    other = tmp_path / "other"
    (other / "silverquillm").mkdir(parents=True)
    monkeypatch.setattr(provenance, "PACKAGE", other / "silverquillm")
    with pytest.raises(provenance.PackageSourceError) as refused:
        REQUIRE_PACKAGE_FROM(checkout)
    message = str(refused.value)
    assert str(other / "silverquillm") in message and str(checkout / "silverquillm") in message
    assert f"PYTHONPATH={checkout}" in message


def test_the_bench_roots_own_package_passes_even_through_a_link(checkout, tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "PACKAGE", checkout / "silverquillm")
    REQUIRE_PACKAGE_FROM(checkout)
    (tmp_path / "linked").symlink_to(checkout)
    REQUIRE_PACKAGE_FROM(tmp_path / "linked")


def test_allow_dirty_does_not_admit_another_checkouts_package(checkout, tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "require_package_from", REQUIRE_PACKAGE_FROM)
    monkeypatch.setattr(provenance, "PACKAGE", tmp_path / "other/silverquillm")
    with pytest.raises(provenance.PackageSourceError):
        provenance.collect({provenance.RECIPE_LABEL: "a" * 40}, checkout, allow_dirty=True)


def test_a_regrade_from_another_checkouts_package_is_refused(edited, tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "require_package_from", REQUIRE_PACKAGE_FROM)
    with pytest.raises(provenance.PackageSourceError):
        regrade(**_another_host(edited, tmp_path, OtherHostDocker()))
    assert not (tmp_path / "regrade").exists()


GUARD = (
    "import sys; from pathlib import Path; from silverquillm.karn import provenance;"
    "provenance.require_package_from(Path(sys.argv[1])); print(provenance.PACKAGE)"
)


def _launch(tmp_path, bench_root, how):
    """Run the rule in a fresh interpreter that finds silverquillm in this repo *how*."""
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if how == "pythonpath":
        command = [sys.executable, "-c", GUARD, str(bench_root)]
        environment["PYTHONPATH"] = str(REPO)
    else:  # a path-entry editable install: a .pth line naming the checkout
        site_dir = tmp_path / "site"
        site_dir.mkdir(exist_ok=True)
        (site_dir / "repo.pth").write_text(f"{REPO}\n")
        command = [
            sys.executable,
            "-I",
            "-c",
            f"import site; site.addsitedir({str(site_dir)!r}); {GUARD}",
            str(bench_root),
        ]
    return subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize("how", ["pythonpath", "editable_install"])
def test_a_fresh_interpreter_checks_where_it_found_the_package(tmp_path, how):
    accepted = _launch(tmp_path, REPO, how)
    assert accepted.returncode == 0, accepted.stderr
    assert Path(accepted.stdout.strip()).resolve() == REPO / "silverquillm"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    refused = _launch(tmp_path, elsewhere, how)
    assert refused.returncode != 0
    assert "package_source_mismatch" in refused.stderr
    assert str(REPO / "silverquillm") in refused.stderr


def test_a_record_carries_its_provenance_and_malformed_provenance_is_invalid(edited_template):
    opts, record = edited_template.opts, edited_template.record
    assert record.run_metadata["provenance"]["host_label"] == "test-host"
    run_input = json.loads((opts["results_dir"] / "edited/run-input.json").read_text())
    assert run_input["provenance"] == record.run_metadata["provenance"]
    broken = json.loads(json.dumps(record.manifest))
    broken["run_metadata"]["provenance"]["dirty_reasons"] = ["bench_checkout_dirty"]
    with pytest.raises(InvalidRunRecordError, match="provenance"):
        KarnRunRecord(broken, record.scores).validate()


# ---- exclusions -----------------------------------------------------------------------------


def edit(record: KarnRunRecord, change) -> KarnRunRecord:
    manifest = json.loads(json.dumps(record.manifest))
    change(manifest["run_metadata"])
    return KarnRunRecord(manifest, record.scores)


def measured(turns, threads="absent"):
    def change(metadata):
        metadata["measurements"]["agent_turns"]["total"]["value"] = turns
        if threads == "absent":
            metadata["measurements"].pop("subagent_threads", None)
        else:
            metadata["measurements"]["subagent_threads"] = threads

    return change


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (measured(40, 0), None),
        (measured(None, None), None),
        (measured(0, 0), "never_executed"),
        (measured(40, 2), "subagents_used"),
        (measured(40), "subagents_uncounted"),
        (lambda m: m["execution"].update(status="host_failed"), "host_failed"),
    ],
)
def test_rules_exclude_only_on_observed_facts(edited_template, change, reason):
    record = edited_template.record
    matched = rule_exclusion(edit(record, change))
    assert (matched and matched[0]) == reason


def write_record_with(opts, run_id, change):
    """Record a run, then rewrite its manifest in place as a record with *change* would be."""
    run_benchmark(**opts, run_id=run_id)
    path = next(opts["results_repo"].glob(f"results/*/{run_id}/manifest.json"))
    manifest = json.loads(path.read_text())
    change(manifest["run_metadata"])
    path.write_text(json.dumps(manifest))
    return read_record(path.parent)


def record_as(opts, record: KarnRunRecord, run_id: str, change) -> KarnRunRecord:
    """Publish *record* again under *run_id*, changed, without running anything; for checks
    that read records but never grade their workspaces."""
    manifest = json.loads(json.dumps(record.manifest))
    manifest["run_id"] = run_id
    change(manifest["run_metadata"])
    return read_record(write_record(opts["results_repo"], KarnRunRecord(manifest, record.scores)))


def test_a_run_meeting_a_rule_is_excluded_when_its_record_is_written(tmp_path, monkeypatch):
    opts = options(tmp_path)
    original = execution.write_record

    def zero_turns(repo, record):
        record.run_metadata["measurements"]["agent_turns"]["total"]["value"] = 0
        return original(repo, record)

    monkeypatch.setattr(execution, "write_record", zero_turns)
    record = run_benchmark(**opts, run_id="refusal")
    exclusion = load_exclusions(opts["results_repo"])["refusal"]
    assert (exclusion.reason, exclusion.source) == ("never_executed", "rule")
    assert exclusion.candidate_hash == record.candidate.hash


def test_operator_exclusions_check_and_rule_backfill(edited):
    opts, record = edited
    repo = opts["results_repo"]
    record_as(opts, record, "old", measured(40))
    record_as(opts, record, "retry", measured(40, 0))

    report = check(repo)
    assert report["unexcluded_rule_matches"] == [
        {"run_id": "old", "candidate_hash": report["unexcluded_rule_matches"][0]["candidate_hash"],
         "rule": "subagents_uncounted"},
    ]  # fmt: skip

    with pytest.raises(ExclusionError, match="superseded_by_required"):
        exclude(repo, "edited", reason="superseded", note="rerun", excluded_by="op")
    with pytest.raises(ExclusionError, match="superseding_run_not_recorded"):
        exclude(repo, "edited", reason="superseded", note="n", excluded_by="op", superseded_by="x")
    exclude(
        repo, "edited", reason="superseded", note="rerun", excluded_by="op", superseded_by="retry"
    )
    with pytest.raises(ExclusionError, match="run_already_excluded"):
        exclude(repo, "edited", reason="other", note="again", excluded_by="op")

    assert [row["run_id"] for row in check(repo, write_rules=True)["written"]] == ["old"]
    assert check(repo) == {
        "unexcluded_rule_matches": [],
        "written": [],
        "orphaned_exclusions": [],
        "missing_superseding_runs": [],
    }
    assert {e.run_id: e.reason for e in load_exclusions(repo).values()} == {
        "edited": "superseded",
        "old": "subagents_uncounted",
    }


def test_a_misplaced_or_malformed_exclusion_is_refused(edited):
    opts, _ = edited
    repo = opts["results_repo"]
    exclusion = exclude(repo, "edited", reason="pilot", note="validation", excluded_by="op")
    path = repo / "exclusions" / exclusion.candidate_hash / "edited.json"
    moved = repo / "exclusions" / ("e" * 64) / "edited.json"
    moved.parent.mkdir()
    shutil.move(path, moved)
    with pytest.raises(ExclusionError, match="exclusion_misplaced"):
        load_exclusions(repo)
    moved.write_text('{"run_id": "edited"}')
    with pytest.raises(ExclusionError, match="exclusion_invalid"):
        load_exclusions(repo)


def test_exclusion_commands(edited):
    opts, _ = edited
    repo = str(opts["results_repo"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["results", "exclude", "edited", "--reason", "subagents_used", "--note",
         "Sonnet delegated to Opus subagents", "--by", "op", "--results-repo", repo],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    listed = runner.invoke(main, ["results", "exclusions", "--results-repo", repo])
    assert "subagents_used" in listed.output and "Opus subagents" in listed.output
    assert runner.invoke(main, ["results", "check", "--results-repo", repo]).exit_code == 0
    unknown = runner.invoke(
        main,
        ["results", "exclude", "nope", "--reason", "other", "--note", "n", "--results-repo", repo],
    )
    assert unknown.exit_code == 1 and "run_not_recorded" in unknown.output


# ---- relative results paths ----------------------------------------------------------------------


def test_runs_sharing_a_baseline_archive_through_a_relative_results_repo(edited, monkeypatch):
    opts, _ = edited
    repo = opts["results_repo"]
    monkeypatch.chdir(repo.parent)
    relative = {**opts, "results_repo": Path(repo.name)}

    for run_id in ("second", "third"):
        record = run_benchmark(**relative, run_id=run_id)
        attachments = json.loads(
            (opts["results_dir"] / run_id / f"results-attachments.{run_id}.json").read_text()
        )
        assert attachments["workspace"]["status"] == "archived", attachments
        assert (archive_dir(repo, record.candidate.hash, run_id) / "workspace.json").is_file()
    assert len(list((repo / "baselines").iterdir())) == 1


def test_relative_paths_backfill_and_materialize(edited, monkeypatch, tmp_path):
    opts, record = edited
    repo, results_dir = opts["results_repo"], opts["results_dir"]
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    monkeypatch.chdir(tmp_path)

    rows = backfill(Path(repo.relative_to(tmp_path)), Path(results_dir.relative_to(tmp_path)))
    rebuilt = materialize(Path(repo.relative_to(tmp_path)), record, Path("rebuilt"))

    assert [row["status"] for row in rows] == ["archived"]
    assert rebuilt.is_absolute()
    assert tree_bytes(rebuilt) == tree_bytes(
        results_dir / "edited" / "workspace_final", graded_only=True
    )


def test_a_run_whose_archive_failed_is_repaired_by_a_later_backfill(tmp_path, monkeypatch):
    opts = options(tmp_path, host=EditingHost())
    readme = opts["bench_root"] / "benchmarks/example/workspace/docs/readme.txt"
    readme.parent.mkdir()
    readme.write_text("deleted by the agent\n")

    def unavailable(*args, **kwargs):
        raise ArchiveRefused("workspace_archive_locked")

    monkeypatch.setattr(execution, "archive_run", unavailable)
    record = run_benchmark(**opts, run_id="retry")
    attachments = json.loads(
        (opts["results_dir"] / "retry" / "results-attachments.retry.json").read_text()
    )
    assert attachments["workspace"] == {"status": "refused", "reason": "workspace_archive_locked"}
    assert read_record(next(opts["results_repo"].glob("results/*/retry")))
    monkeypatch.undo()
    monkeypatch.chdir(tmp_path)

    rows = backfill(
        Path(opts["results_repo"].relative_to(tmp_path)),
        Path(opts["results_dir"].relative_to(tmp_path)),
    )

    assert [row["status"] for row in rows] == ["archived"]
    assert (archive_dir(opts["results_repo"], record.candidate.hash, "retry")).is_dir()


def test_a_corrupt_baseline_is_refused_through_a_relative_path_and_kept(edited, monkeypatch):
    opts, record = edited
    repo = opts["results_repo"]
    [bundle] = (repo / "baselines").iterdir()
    shutil.rmtree(archive_dir(repo, record.candidate.hash, record.run_id))
    bundle.write_bytes(b"not a bundle")
    monkeypatch.chdir(repo.parent)

    with pytest.raises(ArchiveRefused, match="git_failed:bundle"):
        archive_run(Path(repo.name), record, opts["results_dir"] / "edited")
    assert bundle.read_bytes() == b"not a bundle"


# ---- rules never exclude on unknown measurements ---------------------------------------------


@pytest.mark.parametrize("blank", [None, {}])
def test_absent_or_empty_measurements_never_exclude(edited, blank):
    opts, record = edited
    assert rule_exclusion(edit(record, lambda m: m.update(measurements=blank))) is None

    def failed(metadata):
        metadata.update(measurements=blank)
        metadata["execution"]["status"] = "host_failed"

    assert rule_exclusion(edit(record, failed)) == ("host_failed", "execution status host_failed")

    blank_record = record_as(opts, record, "blank", lambda m: m.update(measurements=blank))
    report = check(opts["results_repo"], write_rules=True)
    assert "blank" not in [row["run_id"] for row in report["written"]]
    assert "blank" not in load_exclusions(opts["results_repo"])
    assert not (
        opts["results_repo"] / "exclusions" / blank_record.candidate.hash / "blank.json"
    ).exists()


def test_historical_measurements_without_a_thread_count_are_still_uncounted(edited_template):
    record = edited_template.record
    assert rule_exclusion(edit(record, measured(40)))[0] == "subagents_uncounted"


# ---- regrade summaries apply exclusions ------------------------------------------------------


def regrade_with(opts, out, docker=None, **changes):
    return regrade(
        bench_root=opts["bench_root"],
        benchmark_id="example",
        results_repo=opts["results_repo"],
        results_dir=opts["results_dir"],
        out=out,
        docker=docker or LocalDocker(),
        **changes,
    )


def cohort_runs(summary):
    return sum(row["runs"] for row in summary["cohorts"])


def test_regrade_summaries_leave_out_excluded_runs_and_list_them(edited, tmp_path):
    opts, _ = edited
    write_record_with(opts, "old", measured(40))
    run_benchmark(**opts, run_id="kept")
    repo = opts["results_repo"]
    exclude(repo, "edited", reason="pilot", note="pipeline validation", excluded_by="op")
    check(repo, write_rules=True)

    summary = regrade_with(opts, tmp_path / "regrade")

    assert cohort_runs(summary) == 1
    assert {(row["run_id"], row["reason"]) for row in summary["excluded"]} == {
        ("edited", "pilot"),
        ("old", "subagents_uncounted"),
    }
    assert {row["note"] for row in summary["excluded"]} >= {"pipeline validation"}
    assert len(list((tmp_path / "regrade").glob("*/*.json"))) == 3


def test_an_all_excluded_or_explicitly_selected_excluded_run_has_no_cohort(edited, tmp_path):
    opts, _ = edited
    exclude(opts["results_repo"], "edited", reason="pilot", note="n", excluded_by="op")

    summary = regrade_with(opts, tmp_path / "regrade", runs=["edited"])

    assert summary["cohorts"] == []
    assert [row["run_id"] for row in summary["excluded"]] == ["edited"]


def test_a_malformed_exclusion_stops_the_regrade_before_grading(edited, tmp_path):
    opts, record = edited
    path = opts["results_repo"] / "exclusions" / record.candidate.hash / "edited.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"run_id": "edited"}')
    docker = LocalDocker()

    with pytest.raises(ExclusionError, match="exclusion_invalid"):
        regrade_with(opts, tmp_path / "regrade", docker=docker)
    assert docker.runs == []


def test_exclusions_apply_to_reused_outputs_and_are_never_cached(edited, tmp_path):
    opts, record = edited
    run_benchmark(**opts, run_id="kept")
    out = tmp_path / "regrade"
    assert cohort_runs(regrade_with(opts, out)) == 2

    exclude(opts["results_repo"], "edited", reason="other", note="later", excluded_by="op")
    docker = LocalDocker()
    summary = regrade_with(opts, out, docker=docker)
    assert docker.runs == []
    assert cohort_runs(summary) == 1
    assert "excluded" not in json.loads(next(out.glob("*/edited.json")).read_text())

    (opts["results_repo"] / "exclusions" / record.candidate.hash / "edited.json").unlink()
    summary = regrade_with(opts, out, docker=docker)
    assert docker.runs == []
    assert cohort_runs(summary) == 2
    assert summary["excluded"] == []


def test_the_regrade_command_lists_excluded_runs_beneath_the_table(edited, tmp_path, monkeypatch):
    from silverquillm.karn import regrade as regrade_module

    opts, _ = edited
    exclude(opts["results_repo"], "edited", reason="pilot", note="pipeline check", excluded_by="op")
    monkeypatch.setattr(regrade_module, "DockerRunner", LocalDocker)
    arguments = [
        "regrade", "--benchmark", "example", "--out", str(tmp_path / "regrade"),
        "--bench-root", str(opts["bench_root"]),
        "--results-repo", str(opts["results_repo"]),
        "--results-dir", str(opts["results_dir"]),
    ]  # fmt: skip

    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 0, result.output
    _, _, excluded = result.output.partition("excluded from the comparison:")
    assert "pilot" in excluded and "pipeline check" in excluded
