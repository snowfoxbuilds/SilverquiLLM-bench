"""``scripts/promote_candidate.py`` — the promote gate (#66 Part A).

Every fixture is a real export through TheOzolith's tooling; promotion is
exercised end to end against a temporary ``candidates/`` tree.  The tests
prove: vendor-at-promote is strict (a referenced knowledge tree must exist and
carry its ``PUBLISHABLE`` marker), the *whole* staged tree is scanned for
every credential family the production detector knows (source-only files,
the marker, policy source, binary files) and a refusal never echoes the
value, the generated README names no host-local path, dedup is by identity
*and* source (an operator-edited README is a no-op; a tampered, missing or
differing vendored source is a refusal that leaves the existing directory
untouched), conflicting content under the identity's name is refused, the
vendored copy re-exports byte for byte with no registry access, every
refusal leaves the tree untouched, and no git command is ever executed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import credential_shapes, load_candidate_bundle
from tests.candidate_fixtures import (
    DIGEST_A,
    DIGEST_B,
    FAKE_ANTHROPIC_KEY,
    FAKE_CREDENTIALS,
    NOW,
    SLOT_ASSIGNMENTS,
    SLOT_MENTIONS,
    make_source,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


promote_mod = _load_script("promote_candidate")

TYPE = "knowledge-claude"
PINNED_BASE = f"ghcr.io/acme/theozolith-run-claude:1.2.3@{DIGEST_A}"


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record every subprocess launch and refuse any git invocation."""
    calls: list[list[str]] = []

    def _guard(real):
        def wrapper(args, *a, **kw):
            argv = [str(x) for x in (args if isinstance(args, (list, tuple)) else [args])]
            calls.append(argv)
            if any(Path(part).name == "git" for part in argv[:1]) or "git" in argv[:1]:
                raise AssertionError(f"promotion ran git: {argv}")
            return real(args, *a, **kw)

        return wrapper

    for name in ("run", "Popen", "check_output", "check_call", "call"):
        monkeypatch.setattr(subprocess, name, _guard(getattr(subprocess, name)))
    monkeypatch.setattr(os, "system", lambda cmd: (_ for _ in ()).throw(AssertionError(cmd)))
    return calls


def _source(root: Path, *, publishable: bool = True, **kwargs) -> Path:
    kwargs.setdefault("name", TYPE)
    kwargs.setdefault("knowledge", True)
    source = make_source(root, **kwargs)
    if kwargs["knowledge"] and publishable:
        (source / "knowledge" / "gold" / promote_mod.PUBLISHABLE_MARKER).write_text(
            "MIT — published with the candidate\n", encoding="utf-8"
        )
    return source


def _promote(source: Path, candidates: Path, **kwargs):
    kwargs.setdefault("resolve_digest", lambda ref: DIGEST_A)
    kwargs.setdefault("now", lambda: NOW)
    return promote_mod.promote(source, kwargs.pop("worker_type", TYPE), candidates_dir=candidates, **kwargs)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _entries(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir()) if root.is_dir() else []


class TestPromote:
    def test_promotes_a_definition_with_publishable_knowledge(
        self, tmp_path: Path, no_git: list[list[str]]
    ) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        result = _promote(source, candidates)

        assert result.written is True and result.base_pinned_at_promote is True
        bundle = result.bundle
        target = candidates / f"{TYPE}--{bundle.hash8}"
        assert result.candidate_dir == target and target.is_dir()
        assert _entries(candidates) == [target.name]  # no staging leftovers
        assert _entries(target) == ["README.md", "bundle", "source"]
        # The bundle is a verified export whose recomputed identity names the dir.
        ingested = load_candidate_bundle(target)
        assert ingested.candidate_hash == bundle.candidate_hash
        assert ingested.knowledge == "knowledge/gold" and ingested.knowledge_pin
        assert (target / "bundle" / "knowledge").is_dir()
        # The knowledge SOURCE tree is vendored whole, marker included.
        assert (target / "source" / "knowledge" / "gold" / "AGENTS.md").read_text() == "# golden knowledge\n"
        assert (target / "source" / "knowledge" / "gold" / promote_mod.PUBLISHABLE_MARKER).is_file()
        # The definition is vendored with its base pinned by the resolved digest.
        toml_text = (target / "source" / "worker-types" / f"{TYPE}.toml").read_text()
        assert f'base = "{PINNED_BASE}"' in toml_text
        assert 'knowledge = "knowledge/gold"' in toml_text
        # README stub: identity documented, operator work marked.
        readme = (target / "README.md").read_text()
        for value in (bundle.candidate_hash, bundle.instruction_hash, bundle.base_digest, bundle.adapter, bundle.model):
            assert value in readme
        assert promote_mod.README_TODO_MARKER in readme
        assert "What this candidate varies" in readme
        assert not any("git" in argv[:1] for argv in no_git)

    def test_refuses_knowledge_without_the_publishable_marker(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path, publishable=False)
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert promote_mod.PUBLISHABLE_MARKER in message
        assert "cannot be promoted" in message and "results cannot be published" in message
        assert _entries(candidates) == []

    def test_refuses_a_referenced_knowledge_tree_that_is_absent(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        import shutil

        shutil.rmtree(source / "knowledge" / "gold")
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        assert "absent" in str(info.value) and "cannot be promoted" in str(info.value)
        assert _entries(candidates) == []

    def test_a_definition_without_knowledge_needs_no_marker(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path, name="plain-claude", knowledge=False)
        candidates = tmp_path / "candidates"
        result = _promote(source, candidates, worker_type="plain-claude")
        assert result.written and result.bundle.knowledge == ""
        assert not (result.candidate_dir / "source" / "knowledge").exists()
        assert not (result.candidate_dir / "bundle" / "knowledge").exists()

    def test_the_vendored_copy_reexports_byte_for_byte_with_no_registry(
        self, tmp_path: Path, no_git
    ) -> None:
        source = _source(tmp_path)
        result = _promote(source, tmp_path / "candidates")
        target = result.candidate_dir
        exported_at = json.loads((target / "bundle" / "candidate.json").read_text())["exported_at"]
        out = tmp_path / "reexport"
        # No resolve_digest and no docker config: the vendored source is digest-pinned.
        ozcandidate.export_candidate(target / "source", TYPE, out, now=lambda: exported_at)
        assert _snapshot(out) == _snapshot(target / "bundle")

    def test_a_digest_pinned_source_definition_is_copied_verbatim(self, tmp_path: Path, no_git) -> None:
        source = _source(
            tmp_path,
            base=PINNED_BASE,
            extra_lines=("# a comment the copy must keep",),
        )
        original = (source / "worker-types" / f"{TYPE}.toml").read_bytes()
        result = _promote(source, tmp_path / "candidates", resolve_digest=None)
        assert result.base_pinned_at_promote is False
        assert (result.candidate_dir / "source" / "worker-types" / f"{TYPE}.toml").read_bytes() == original

    def test_same_identity_again_is_a_no_op(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        first = _promote(source, candidates)
        before = _snapshot(candidates)
        # A later export of the same definition (new exported_at) is the same identity.
        again = _promote(source, candidates, now=lambda: "2026-09-04T00:00:00Z")
        assert again.written is False and again.candidate_dir == first.candidate_dir
        assert again.bundle.candidate_hash == first.bundle.candidate_hash
        assert _snapshot(candidates) == before
        assert any("already promoted" in note for note in again.notes)

    def test_conflicting_content_under_the_identitys_name_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        first = _promote(source, candidates)
        dockerfile = first.candidate_dir / "bundle" / "Dockerfile"
        dockerfile.write_text(dockerfile.read_text() + "RUN echo tampered\n")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        assert "not this candidate" in str(info.value)
        assert _snapshot(candidates) == before

    def test_the_same_identity_under_another_slug_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        first = _promote(source, candidates, slug="alpha")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates, slug="beta")
        assert str(first.candidate_dir) in str(info.value) and "deduplicating" in str(info.value)
        assert _snapshot(candidates) == before

    def test_a_different_identity_is_a_second_directory(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        first = _promote(source, candidates)
        second = _promote(source, candidates, resolve_digest=lambda ref: DIGEST_B)
        assert second.written and second.candidate_dir != first.candidate_dir
        assert second.bundle.candidate_hash != first.bundle.candidate_hash
        assert _entries(candidates) == sorted([first.candidate_dir.name, second.candidate_dir.name])

    def test_dry_run_writes_nothing(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        result = _promote(source, candidates, dry_run=True)
        assert result.written is False and any("dry run" in n for n in result.notes)
        assert _entries(candidates) == []

    def test_a_secret_value_in_the_knowledge_tree_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        (source / "knowledge" / "gold" / "AGENTS.md").write_text(
            f"# golden knowledge\n\nuse {FAKE_ANTHROPIC_KEY}\n", encoding="utf-8"
        )
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        assert "refused by the bench" in str(info.value)
        assert FAKE_ANTHROPIC_KEY not in str(info.value)
        assert _entries(candidates) == []

    def test_a_symlink_in_the_knowledge_source_tree_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        (source / "knowledge" / "gold" / "escape").symlink_to(tmp_path)
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused):
            _promote(source, candidates)
        assert _entries(candidates) == []

    def test_unknown_worker_type_or_source_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        with pytest.raises(promote_mod.PromotionRefused):
            _promote(source, tmp_path / "candidates", worker_type="nope")
        with pytest.raises(promote_mod.PromotionRefused):
            _promote(tmp_path / "missing", tmp_path / "candidates")


class TestWholeTreeSecretScan:
    """The compiled bundle is not the only thing that goes public: knowledge
    and policy SOURCE, the ``PUBLISHABLE`` marker and the README travel too,
    so the complete staged tree is held to the production detector."""

    def test_refuses_an_aws_key_in_the_publishable_marker(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        sample = FAKE_CREDENTIALS["AWS access key id"]
        (source / "knowledge" / "gold" / promote_mod.PUBLISHABLE_MARKER).write_text(
            f"MIT\n# scratch: {sample}\n", encoding="utf-8"
        )
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "promoted tree" in message and "PUBLISHABLE" in message and "AWS access key id" in message
        assert sample not in message
        assert _entries(candidates) == []

    @pytest.mark.parametrize("family", sorted(FAKE_CREDENTIALS))
    def test_refuses_every_credential_family_in_a_source_only_knowledge_file(self, tmp_path: Path, no_git, family: str) -> None:
        # A root-level file the knowledge compiler ignores: it never reaches
        # the bundle, so only a scan of the vendored source can catch it.
        source = _source(tmp_path)
        sample = FAKE_CREDENTIALS[family]
        (source / "knowledge" / "gold" / "NOTES.md").write_text(f"# notes\n\n{sample}\n", encoding="utf-8")
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "promoted tree" in message and "NOTES.md" in message
        label = "assigned to secret slot" if family.startswith("a value") else family
        assert label in message
        for line in sample.splitlines():
            assert line not in message
        assert _entries(candidates) == []

    def test_the_fixture_families_cover_the_production_detector(self) -> None:
        assert set(FAKE_CREDENTIALS) == set(credential_shapes())

    @pytest.mark.parametrize("form", sorted(SLOT_ASSIGNMENTS))
    def test_refuses_a_declared_slot_assigned_a_value_of_any_shape(self, tmp_path: Path, no_git, form: str) -> None:
        """Length, character class and quoting are not what makes a value a
        secret: a one-letter bare value, a symbol-laden YAML scalar, a quoted
        JSON pair and a placeholder in angle brackets all refuse, naming the
        file and the shape and never the line."""
        line = SLOT_ASSIGNMENTS[form]
        source = _source(tmp_path)
        (source / "knowledge" / "gold" / "NOTES.md").write_text(f"# notes\n\n{line}\n", encoding="utf-8")
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "NOTES.md: a value assigned to secret slot ANTHROPIC_API_KEY" in message
        assert line not in message
        value = line.split("=" if "=" in line.split(":")[0] else ":", 1)[1].strip().strip("\"'")
        assert not value or len(value) < 2 or value not in message
        assert _entries(candidates) == []

    @pytest.mark.parametrize("form", sorted(SLOT_MENTIONS))
    def test_a_slot_declared_mentioned_or_assigned_nothing_promotes(self, tmp_path: Path, no_git, form: str) -> None:
        """The slot's name in a declaration list, in prose, or assigned an
        empty value — the shape the vendored definition's own ``[secrets]``
        table takes — is not a value and never blocks promotion."""
        line = SLOT_MENTIONS[form]
        source = _source(tmp_path)
        (source / "knowledge" / "gold" / "NOTES.md").write_text(f"# notes\n\n{line}\n", encoding="utf-8")
        result = _promote(source, tmp_path / "candidates")
        vendored = result.candidate_dir / "source" / "knowledge" / "gold" / "NOTES.md"
        assert vendored.read_text(encoding="utf-8").splitlines()[-1] == line

    @pytest.mark.parametrize("family", ["GitHub token", "Slack token"])
    def test_a_credential_in_agent_policy_source_never_promotes_or_echoes(self, tmp_path: Path, no_git, family: str) -> None:
        # TheOzolith's export admits only allowlisted JSON drop-ins in a policy
        # tree (ADR-0055), so a credential there is refused before anything is
        # vendored — and the refusal still names no value.
        source = _source(tmp_path, policy=True)
        sample = FAKE_CREDENTIALS[family]
        (source / "policy" / "gold" / "notes.json").write_text(json.dumps({"note": sample}) + "\n", encoding="utf-8")
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        assert "export failed" in str(info.value) and sample not in str(info.value)
        assert _entries(candidates) == []

    @pytest.mark.parametrize("family", ["GitHub token", "Slack token"])
    def test_the_staged_tree_scan_covers_vendored_policy_source(self, tmp_path: Path, no_git, family: str) -> None:
        """Whatever the export admits tomorrow, the scan before the rename
        covers ``source/policy/`` like every other staged file."""
        import shutil

        source = _source(tmp_path, policy=True)
        result = _promote(source, tmp_path / "candidates")
        staging = tmp_path / "staging"
        shutil.copytree(result.candidate_dir, staging)
        sample = FAKE_CREDENTIALS[family]
        (staging / "source" / "policy" / "gold" / "attribution.json").write_text(
            json.dumps({"attribution": {"sessionUrl": False}, "x": sample}) + "\n", encoding="utf-8"
        )
        with pytest.raises(promote_mod.PromotionRefused) as info:
            promote_mod.refuse_credentials(staging, result.bundle)
        message = str(info.value)
        assert "source/policy/gold/attribution.json" in message and family in message and sample not in message

    def test_refuses_a_credential_hidden_in_a_binary_file_without_printing_it(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        blob = b"\x00\x01\xff\xfe" * 16 + FAKE_CREDENTIALS["GitHub fine-grained token"].encode() + b"\x00\x80" * 8
        (source / "knowledge" / "gold" / "blob.bin").write_bytes(blob)
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "blob.bin" in message and "GitHub fine-grained token" in message
        assert FAKE_CREDENTIALS["GitHub fine-grained token"] not in message and "\xff" not in message
        assert _entries(candidates) == []

    def test_refuses_an_unreadable_source_file_safely(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        secret = source / "knowledge" / "gold" / "locked.txt"
        secret.write_text("cannot be cleared\n", encoding="utf-8")
        secret.chmod(0)
        try:
            if os.access(secret, os.R_OK):
                pytest.skip("running with privileges that ignore file modes")
            candidates = tmp_path / "candidates"
            with pytest.raises(promote_mod.PromotionRefused) as info:
                _promote(source, candidates)
            assert "locked.txt" in str(info.value) and "cannot be cleared" not in str(info.value)
            assert _entries(candidates) == []
        finally:
            secret.chmod(0o644)

    def test_dry_run_refuses_the_same_and_echoes_nothing(self, tmp_path: Path, no_git, capsys) -> None:
        source = _source(tmp_path, base=PINNED_BASE)
        sample = FAKE_CREDENTIALS["Slack token"]
        (source / "knowledge" / "gold" / promote_mod.PUBLISHABLE_MARKER).write_text(f"MIT {sample}\n", encoding="utf-8")
        candidates = tmp_path / "candidates"
        assert promote_mod.main([str(source), TYPE, "--candidates-dir", str(candidates), "--dry-run"]) == 1
        captured = capsys.readouterr()
        assert "REFUSED" in captured.err and sample not in captured.err and sample not in captured.out
        assert _entries(candidates) == []


class TestNoHostPaths:
    def test_the_generated_readme_names_no_host_local_path(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        result = _promote(source, tmp_path / "candidates")
        readme = (result.candidate_dir / "README.md").read_text(encoding="utf-8")
        for needle in (str(source), str(source.resolve()), str(tmp_path), str(Path.home()), os.environ.get("USER", "\0")):
            assert needle not in readme, needle
        assert "the operator's Config Repo" in readme
        assert "Config Repo revision" in readme and promote_mod.README_TODO_MARKER in readme
        # Nothing generated under the candidate carries the Config Repo path either.
        for path in result.candidate_dir.rglob("*"):
            if path.is_file():
                assert str(source).encode() not in path.read_bytes(), path

    def test_a_definition_that_names_the_config_repo_path_is_refused(self, tmp_path: Path, no_git) -> None:
        source = _source(tmp_path)
        source_resolved = source.resolve()
        source = _source(tmp_path, extra_lines=(f"# exported from {source_resolved}",))
        candidates = tmp_path / "candidates"
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "Config Repo" in message and "host-local" in message
        assert str(source_resolved) not in message, "the diagnostic names the kind of path, not the path"
        assert _entries(candidates) == []


class TestSourceAwareDedup:
    def _promoted(self, tmp_path: Path):
        source = _source(tmp_path)
        candidates = tmp_path / "candidates"
        first = _promote(source, candidates)
        return source, candidates, first

    def test_an_operator_edited_readme_is_still_a_no_op(self, tmp_path: Path, no_git) -> None:
        source, candidates, first = self._promoted(tmp_path)
        readme = first.candidate_dir / "README.md"
        readme.write_text("# completed by the operator\n\nWhat this candidate varies: the knowledge tree.\n", encoding="utf-8")
        before = _snapshot(candidates)
        again = _promote(source, candidates, now=lambda: "2026-09-04T00:00:00Z")
        assert again.written is False and again.candidate_dir == first.candidate_dir
        assert _snapshot(candidates) == before, "the edited README survives untouched"
        assert any("equivalent vendored source" in note for note in again.notes)

    def test_tampered_vendored_source_is_refused_and_left_untouched(self, tmp_path: Path, no_git) -> None:
        source, candidates, first = self._promoted(tmp_path)
        agents = first.candidate_dir / "source" / "knowledge" / "gold" / "AGENTS.md"
        agents.write_text("# golden knowledge\n\ntampered after promotion\n", encoding="utf-8")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "does not reproduce" in message and "left untouched" in message
        assert _snapshot(candidates) == before

    def test_a_tampered_marker_text_in_the_existing_copy_is_refused(self, tmp_path: Path, no_git) -> None:
        # The marker is not compiled, so the existing bundle still re-exports;
        # only the source comparison catches the difference.
        source, candidates, first = self._promoted(tmp_path)
        marker = first.candidate_dir / "source" / "knowledge" / "gold" / promote_mod.PUBLISHABLE_MARKER
        marker.write_text("GPL — changed after promotion\n", encoding="utf-8")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        message = str(info.value)
        assert "differs from the source being promoted" in message and promote_mod.PUBLISHABLE_MARKER in message
        assert "README" in message and "left untouched" in message
        assert _snapshot(candidates) == before

    def test_a_config_repo_whose_source_moved_on_is_refused(self, tmp_path: Path, no_git) -> None:
        # Same identity (an ignored root file moves no pin), different source.
        source, candidates, first = self._promoted(tmp_path)
        (source / "knowledge" / "gold" / "NOTES.md").write_text("added later\n", encoding="utf-8")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused) as info:
            _promote(source, candidates)
        assert "NOTES.md" in str(info.value) and "differs" in str(info.value)
        assert _snapshot(candidates) == before
        assert _entries(candidates) == [first.candidate_dir.name], "no staging leftovers"

    def test_a_missing_vendored_source_is_refused(self, tmp_path: Path, no_git) -> None:
        import shutil

        source, candidates, first = self._promoted(tmp_path)
        shutil.rmtree(first.candidate_dir / "source")
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused, match="no vendored source/"):
            _promote(source, candidates)
        assert _snapshot(candidates) == before

    def test_a_symlink_planted_in_the_existing_source_is_refused(self, tmp_path: Path, no_git) -> None:
        source, candidates, first = self._promoted(tmp_path)
        (first.candidate_dir / "source" / "knowledge" / "gold" / "escape").symlink_to(tmp_path)
        before = _snapshot(candidates)
        with pytest.raises(promote_mod.PromotionRefused):
            _promote(source, candidates)
        assert _snapshot(candidates) == before


class TestPinBase:
    def test_rewrites_exactly_the_top_level_base_line(self) -> None:
        text = (
            "# header comment\n"
            'base = "ghcr.io/acme/img:1.0"  # trailing\n'
            'driver = "builtin:implementer"\n'
            "[secrets]\n"
            'ANTHROPIC_API_KEY = ""\n'
        )
        import tomllib

        data = tomllib.loads(text)
        pinned = f"ghcr.io/acme/img:1.0@{DIGEST_A}"
        out, changed = promote_mod.pin_base_in_definition(text, data, pinned)
        assert changed is True
        assert out.splitlines()[1] == f'base = "{pinned}"  # trailing'
        assert tomllib.loads(out) == dict(data, base=pinned)

    def test_refuses_an_ambiguous_definition(self) -> None:
        import tomllib

        text = "base = 'ghcr.io/acme/img:1.0'\n"  # single quotes: not the one shape handled
        data = tomllib.loads(text)
        with pytest.raises(promote_mod.PromotionRefused):
            promote_mod.pin_base_in_definition(text, data, f"ghcr.io/acme/img:1.0@{DIGEST_A}")


class TestCli:
    def test_main_promotes_and_reports(self, tmp_path: Path, no_git, capsys: pytest.CaptureFixture[str]) -> None:
        source = _source(tmp_path, base=PINNED_BASE)  # digest-pinned: the CLI needs no registry
        candidates = tmp_path / "candidates"
        code = promote_mod.main([str(source), TYPE, "--candidates-dir", str(candidates)])
        assert code == 0
        out = capsys.readouterr().out
        assert "promoted" in out and "approval stamp" in out
        assert len(_entries(candidates)) == 1

    def test_main_refusal_exits_1_and_writes_nothing(
        self, tmp_path: Path, no_git, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _source(tmp_path, base=PINNED_BASE, publishable=False)
        candidates = tmp_path / "candidates"
        code = promote_mod.main([str(source), TYPE, "--candidates-dir", str(candidates)])
        assert code == 1
        assert "REFUSED" in capsys.readouterr().err
        assert _entries(candidates) == []
