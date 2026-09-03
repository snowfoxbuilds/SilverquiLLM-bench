"""``scripts/promote_candidate.py`` — the promote gate (#66 Part A).

Every fixture is a real export through TheOzolith's tooling; promotion is
exercised end to end against a temporary ``candidates/`` tree.  The tests
prove: vendor-at-promote is strict (a referenced knowledge tree must exist and
carry its ``PUBLISHABLE`` marker), dedup is by identity, conflicting content
under the identity's name is refused, the vendored copy re-exports byte for
byte with no registry access, every refusal leaves the tree untouched, and
no git command is ever executed.
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

from silverquillm.candidate import load_candidate_bundle
from tests.candidate_fixtures import DIGEST_A, DIGEST_B, FAKE_ANTHROPIC_KEY, NOW, make_source

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
