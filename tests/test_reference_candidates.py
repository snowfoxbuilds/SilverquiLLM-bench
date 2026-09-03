"""Platform test: every checked-in candidate under ``candidates/`` is a real,
verifiable Candidate Bundle whose recomputed identity matches its directory
name (#65 acceptance).

For each ``candidates/<slug>--<hash8>/``: the wrapped ``bundle/`` ingests
through the bench (TheOzolith's verifier recomputes the identity from bundle
bytes — a tampered manifest, Dockerfile or layout fails here), the ``hash8``
suffix equals the first eight characters of the bench's candidate hash over
the recomputed triple, no secret value is present, the README beside the
bundle documents the identity, and re-exporting the checked-in source
definition reproduces the bundle byte for byte (the export needs no registry
access: the base is digest-pinned in the source).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import BUNDLE_SUBDIR, load_candidate_bundle
from silverquillm.results_repo import OZOLITH_SCHEME, candidate_dirname
from tests.candidate_fixtures import CODEX_BASE, make_candidate_dir

REPO = Path(__file__).resolve().parents[1]
CANDIDATES = REPO / "candidates"
DIRNAME = re.compile(r"(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*?)--(?P<hash8>[0-9a-f]{8})")
FLOATING_MODEL_NAMES = {"sonnet", "opus", "haiku", "fable", "default", "opusplan"}


def _candidate_dirs(root: Path = CANDIDATES) -> list[Path]:
    """Every candidate directory under *root* — discovered, never enumerated:
    a further checked-in candidate joins with nothing to register."""
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def _slug(path: Path) -> str:
    match = DIRNAME.fullmatch(path.name)
    assert match, f"{path.name} is not <slug>--<hash8>"
    return match.group("slug")


CANDIDATE_DIRS = _candidate_dirs()


def test_the_current_vanilla_reference_candidates_are_checked_in() -> None:
    """The two current references must be present; nothing here caps how many
    candidates the tree may hold."""
    slugs = sorted(_slug(path) for path in CANDIDATE_DIRS)
    assert "vanilla-claude" in slugs and "vanilla-codex" in slugs
    assert len(slugs) == len(set(slugs)), "candidates/ is flat and deduplicating"
    assert (CANDIDATES / "README.md").is_file()


def test_discovery_admits_a_further_candidate_with_nothing_to_register(tmp_path: Path) -> None:
    """A candidates tree holding the checked-in references plus a candidate
    that does not exist yet (another adapter/model identity, exported the
    same way) is discovered whole, and every entry ingests through the same
    path — no model registry, no adapter list, no maximum."""
    tree = tmp_path / "candidates"
    tree.mkdir()
    for path in CANDIDATE_DIRS:
        shutil.copytree(path, tree / path.name)
    newcomer = make_candidate_dir(
        tree, slug="future-codex", name="future-codex", adapter="codex",
        model="gpt-5.3-codex", base=CODEX_BASE, secrets=("CODEX_AUTH_JSON",),
    )
    assert newcomer.parent == tree and newcomer.name.startswith("future-codex--")
    discovered = _candidate_dirs(tree)
    assert [p.name for p in discovered] == sorted(
        [p.name for p in CANDIDATE_DIRS] + [newcomer.name]
    )
    assert len(discovered) == len(CANDIDATE_DIRS) + 1
    identities = {}
    for path in discovered:
        bundle = load_candidate_bundle(path)
        assert path.name == candidate_dirname(_slug(path), bundle.identity)
        identities[path.name] = bundle.candidate_hash
    assert len(set(identities.values())) == len(discovered)  # every identity distinct


@pytest.mark.parametrize("candidate_dir", CANDIDATE_DIRS, ids=[p.name for p in CANDIDATE_DIRS])
class TestEveryCheckedInCandidate:
    def test_ingests_and_its_directory_carries_its_recomputed_hash(self, candidate_dir: Path) -> None:
        bundle = load_candidate_bundle(candidate_dir)
        assert bundle.path == candidate_dir and bundle.bundle_path == candidate_dir / BUNDLE_SUBDIR
        assert bundle.identity.scheme == OZOLITH_SCHEME and bundle.identity.verified is True
        assert candidate_dir.name == candidate_dirname(_slug(candidate_dir), bundle.identity)
        assert candidate_dir.name.endswith(bundle.hash8)
        # The bundle verifies on its own through TheOzolith's verifier, and the
        # recorded identity agrees with the recomputed one.
        summary = ozcandidate.verify_bundle(bundle.bundle_path)
        assert (summary.base_digest, summary.instruction_hash, summary.adapter) == (
            bundle.base_digest, bundle.instruction_hash, bundle.adapter,
        )
        assert bundle.base.endswith("@" + bundle.base_digest)

    def test_varies_nothing(self, candidate_dir: Path) -> None:
        """A vanilla reference candidate: stock run image, no setup, no
        knowledge, no policy, the adapter's default model spelled as a pinned
        provider ID, default effort — and the adapter is the slug's."""
        bundle = load_candidate_bundle(candidate_dir)
        assert _slug(candidate_dir) == f"vanilla-{bundle.adapter}"
        assert bundle.setup == () and bundle.knowledge == "" and bundle.policy == ""
        assert bundle.knowledge_pin == "" and bundle.policy_pin == ""
        assert bundle.effort == ""
        assert bundle.model and bundle.model not in FLOATING_MODEL_NAMES
        assert not bundle.model.endswith("-latest")
        assert bundle.driver == "builtin:implementer"
        assert sorted(p.name for p in bundle.bundle_path.iterdir()) == ["Dockerfile", "candidate.json"]

    def test_carries_secret_slot_names_only(self, candidate_dir: Path) -> None:
        bundle = load_candidate_bundle(candidate_dir)  # the loader's scan already refused any value
        assert bundle.secret_slots and all(re.fullmatch(r"[A-Z][A-Z0-9_]*", s) for s in bundle.secret_slots)
        for path in candidate_dir.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                assert "sk-ant-" not in text and "ghp_" not in text and "sk-proj-" not in text

    def test_readme_documents_the_identity(self, candidate_dir: Path) -> None:
        bundle = load_candidate_bundle(candidate_dir)
        readme = (candidate_dir / "README.md").read_text(encoding="utf-8")
        for value in (bundle.candidate_hash, bundle.instruction_hash, bundle.base_digest, bundle.adapter, bundle.model):
            assert value in readme
        assert "varies nothing" in readme

    def test_reexporting_the_checked_in_source_reproduces_the_bundle(self, candidate_dir: Path, tmp_path: Path) -> None:
        slug = _slug(candidate_dir)
        source = candidate_dir / "source"
        assert (source / "worker-types" / f"{slug}.toml").is_file()
        exported_at = json.loads((candidate_dir / BUNDLE_SUBDIR / "candidate.json").read_text())["exported_at"]
        out = tmp_path / "reexport"
        summary = ozcandidate.export_candidate(source, slug, out, now=lambda: exported_at)
        checked_in = sorted(p.relative_to(candidate_dir / BUNDLE_SUBDIR) for p in (candidate_dir / BUNDLE_SUBDIR).rglob("*") if p.is_file())
        fresh = sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file())
        assert checked_in == fresh
        for rel in checked_in:
            assert (out / rel).read_bytes() == (candidate_dir / BUNDLE_SUBDIR / rel).read_bytes(), rel
        assert summary.instruction_hash == load_candidate_bundle(candidate_dir).instruction_hash
