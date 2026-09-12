"""Platform test: every checked-in candidate under ``candidates/`` is a real,
verifiable Candidate Bundle whose recomputed identity matches its directory
name (#65 acceptance; #66 opens the tree to promoted candidates).

For each ``candidates/<slug>--<hash8>/``: the wrapped ``bundle/`` ingests
through the bench (TheOzolith's verifier recomputes the identity from bundle
bytes — a tampered manifest, Dockerfile or layout fails here), the ``hash8``
suffix equals the first eight characters of the bench's candidate hash over
the recomputed triple, no secret value is present, the README beside the
bundle documents the identity and is complete (no promote-time placeholder
left), and re-exporting the checked-in source definition reproduces the
bundle byte for byte (the export needs no registry access: the base is
digest-pinned in the source).  The vanilla reference candidates additionally
vary nothing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest
from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import BUNDLE_SUBDIR, load_candidate_bundle, scan_tree_for_credentials
from silverquillm.results_repo import OZOLITH_SCHEME, candidate_dirname
from tests.candidate_fixtures import (
    CODEX_BASE,
    DIGEST_A,
    FAKE_CREDENTIALS,
    NOW,
    make_candidate_dir,
    make_source,
)

REPO = Path(__file__).resolve().parents[1]
CANDIDATES = REPO / "candidates"
DIRNAME = re.compile(r"(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*?)--(?P<hash8>[0-9a-f]{8})")
FLOATING_MODEL_NAMES = {"sonnet", "opus", "haiku", "fable", "default", "opusplan"}
VANILLA_PREFIX = "vanilla-"
#: The placeholder ``scripts/promote_candidate.py`` leaves in a README stub.
README_TODO_MARKER = "TODO(promote)"


def _load_script(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _candidate_dirs(root: Path = CANDIDATES) -> list[Path]:
    """Every candidate directory under *root* — discovered, never enumerated:
    a further checked-in candidate joins with nothing to register.  Every
    entry must be a real directory in the tree: a symlink under a candidate
    name is rejected, never followed — a checked-in candidate is what the
    repository holds, not what a link on one host points at."""
    found: list[Path] = []
    for path in sorted(root.iterdir()):
        if path.name.startswith("."):
            continue
        mode = path.lstat().st_mode
        assert not stat.S_ISLNK(mode), (
            f"{path} is a symlink: a checked-in candidate is a real directory under"
            f" {root.name}/, never a link to content elsewhere"
        )
        if stat.S_ISDIR(mode):
            found.append(path)
    return found


def _slug(path: Path) -> str:
    match = DIRNAME.fullmatch(path.name)
    assert match, f"{path.name} is not <slug>--<hash8>"
    return match.group("slug")


def _is_vanilla(path: Path) -> bool:
    return _slug(path).startswith(VANILLA_PREFIX)


CANDIDATE_DIRS = _candidate_dirs()


# ---------------------------------------------------------------------------
# The checks every checked-in candidate must pass (shared with the promoted
# fixture below, so a promoted candidate is held to exactly the same bar).
# ---------------------------------------------------------------------------


def check_ingests_and_carries_its_hash(candidate_dir: Path) -> None:
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
    assert bundle.driver == "builtin:implementer"
    assert bundle.model and bundle.model not in FLOATING_MODEL_NAMES
    assert not bundle.model.endswith("-latest")


def check_secret_slot_names_only(candidate_dir: Path) -> None:
    """The bundle's scan refused any value inside ``bundle/``; the *whole*
    candidate directory — README, vendored definition, knowledge and policy
    source, the ``PUBLISHABLE`` marker — is held to the same production
    detector, so a source-only credential fails here too."""
    bundle = load_candidate_bundle(candidate_dir)
    assert bundle.secret_slots and all(re.fullmatch(r"[A-Z][A-Z0-9_]*", s) for s in bundle.secret_slots)
    findings = scan_tree_for_credentials(candidate_dir, secret_slots=bundle.secret_slots, what="candidate entry")
    assert findings == [], (
        f"{candidate_dir.name} carries what looks like a credential (file: shape, value not"
        f" echoed): {'; '.join(str(f) for f in findings)}"
    )


def check_readme_is_complete(candidate_dir: Path) -> None:
    bundle = load_candidate_bundle(candidate_dir)
    readme = (candidate_dir / "README.md").read_text(encoding="utf-8")
    for value in (bundle.candidate_hash, bundle.instruction_hash, bundle.base_digest, bundle.adapter, bundle.model):
        assert value in readme
    assert README_TODO_MARKER not in readme, (
        f"{candidate_dir.name}/README.md still carries the promote-time placeholder"
        f" {README_TODO_MARKER!r}; complete it before committing the candidate"
    )
    if _is_vanilla(candidate_dir):
        assert "varies nothing" in readme
    else:
        assert "What this candidate varies" in readme


def check_source_reexports_the_bundle(candidate_dir: Path, tmp_path: Path) -> None:
    manifest = json.loads((candidate_dir / BUNDLE_SUBDIR / "candidate.json").read_text())
    worker_type = manifest["worker_type"]
    source = candidate_dir / "source"
    assert (source / "worker-types" / f"{worker_type}.toml").is_file()
    out = tmp_path / "reexport"
    summary = ozcandidate.export_candidate(source, worker_type, out, now=lambda: manifest["exported_at"])
    checked_in = sorted(p.relative_to(candidate_dir / BUNDLE_SUBDIR) for p in (candidate_dir / BUNDLE_SUBDIR).rglob("*") if p.is_file())
    fresh = sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file())
    assert checked_in == fresh
    for rel in checked_in:
        assert (out / rel).read_bytes() == (candidate_dir / BUNDLE_SUBDIR / rel).read_bytes(), rel
    assert summary.instruction_hash == load_candidate_bundle(candidate_dir).instruction_hash


def check_vendored_knowledge_is_declared_publishable(candidate_dir: Path) -> None:
    """A candidate that bakes knowledge vendors the source tree, and that tree
    carries the operator's publishable declaration (vendor-at-promote)."""
    bundle = load_candidate_bundle(candidate_dir)
    if not bundle.knowledge:
        assert not (candidate_dir / "source" / "knowledge").exists()
        return
    tree = candidate_dir / "source" / bundle.knowledge
    assert tree.is_dir(), f"{candidate_dir.name} bakes {bundle.knowledge} but vendors no source tree"
    assert (tree / "PUBLISHABLE").is_file(), f"{candidate_dir.name}: {bundle.knowledge} carries no PUBLISHABLE marker"


# ---------------------------------------------------------------------------


def test_the_current_vanilla_reference_candidates_are_checked_in() -> None:
    """The two current references must be present; nothing here caps how many
    candidates the tree may hold."""
    slugs = sorted(_slug(path) for path in CANDIDATE_DIRS)
    assert "vanilla-claude" in slugs and "vanilla-codex" in slugs
    assert len(slugs) == len(set(slugs)), "candidates/ is flat and deduplicating"
    assert (CANDIDATES / "README.md").is_file()


def test_identities_are_distinct_across_the_tree() -> None:
    hashes = [load_candidate_bundle(path).candidate_hash for path in CANDIDATE_DIRS]
    assert len(set(hashes)) == len(hashes), "candidates/ is deduplicating: one directory per identity"


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


def test_discovery_rejects_a_symlinked_candidate_entry(tmp_path: Path) -> None:
    """A correctly named ``<slug>--<hash8>`` entry that is a symlink to a
    valid candidate elsewhere on the host is not a checked-in candidate: the
    repository would hold a link, not the artifact.  Discovery refuses it
    naming the entry, and the real directories beside it are unaffected."""
    tree = tmp_path / "candidates"
    tree.mkdir()
    for path in CANDIDATE_DIRS:
        shutil.copytree(path, tree / path.name)
    external = make_candidate_dir(
        tmp_path / "elsewhere", slug="future-codex", name="future-codex", adapter="codex",
        model="gpt-5.3-codex", base=CODEX_BASE, secrets=("CODEX_AUTH_JSON",),
    )
    load_candidate_bundle(external)  # valid on its own — the link is the problem
    (tree / external.name).symlink_to(external, target_is_directory=True)
    with pytest.raises(AssertionError, match="symlink") as info:
        _candidate_dirs(tree)
    assert external.name in str(info.value)
    (tree / external.name).unlink()
    assert [p.name for p in _candidate_dirs(tree)] == sorted(p.name for p in CANDIDATE_DIRS)


@pytest.mark.parametrize("candidate_dir", CANDIDATE_DIRS, ids=[p.name for p in CANDIDATE_DIRS])
class TestEveryCheckedInCandidate:
    def test_ingests_and_its_directory_carries_its_recomputed_hash(self, candidate_dir: Path) -> None:
        check_ingests_and_carries_its_hash(candidate_dir)

    def test_carries_secret_slot_names_only(self, candidate_dir: Path) -> None:
        check_secret_slot_names_only(candidate_dir)

    def test_readme_documents_the_identity_and_is_complete(self, candidate_dir: Path) -> None:
        check_readme_is_complete(candidate_dir)

    def test_reexporting_the_checked_in_source_reproduces_the_bundle(self, candidate_dir: Path, tmp_path: Path) -> None:
        check_source_reexports_the_bundle(candidate_dir, tmp_path)

    def test_vendored_knowledge_is_declared_publishable(self, candidate_dir: Path) -> None:
        check_vendored_knowledge_is_declared_publishable(candidate_dir)


@pytest.mark.parametrize(
    "candidate_dir",
    [p for p in CANDIDATE_DIRS if _is_vanilla(p)],
    ids=[p.name for p in CANDIDATE_DIRS if _is_vanilla(p)],
)
def test_a_vanilla_reference_candidate_varies_nothing(candidate_dir: Path) -> None:
    """Stock run image, no setup, no knowledge, no policy, the adapter's
    default model spelled as a pinned provider ID, default effort — and the
    adapter is the slug's."""
    bundle = load_candidate_bundle(candidate_dir)
    assert _slug(candidate_dir) == f"{VANILLA_PREFIX}{bundle.adapter}"
    assert bundle.setup == () and bundle.knowledge == "" and bundle.policy == ""
    assert bundle.knowledge_pin == "" and bundle.policy_pin == ""
    assert bundle.effort == ""
    assert sorted(p.name for p in bundle.bundle_path.iterdir()) == ["Dockerfile", "candidate.json"]


class TestAPromotedCandidateMeetsTheSameBar:
    """``scripts/promote_candidate.py`` output, once the operator completes
    the README, passes every check a checked-in candidate must pass."""

    @pytest.fixture
    def promoted(self, tmp_path: Path) -> Path:
        promote_mod = _load_script("promote_candidate")
        source = make_source(tmp_path, name="knowledge-claude", knowledge=True)
        (source / "knowledge" / "gold" / "PUBLISHABLE").write_text("MIT\n", encoding="utf-8")
        result = promote_mod.promote(
            source,
            "knowledge-claude",
            candidates_dir=tmp_path / "candidates",
            resolve_digest=lambda ref: DIGEST_A,
            now=lambda: NOW,
        )
        return result.candidate_dir

    def test_the_stub_readme_is_refused_until_completed(self, promoted: Path) -> None:
        with pytest.raises(AssertionError, match="placeholder"):
            check_readme_is_complete(promoted)

    def test_the_platform_check_catches_a_source_only_credential(self, promoted: Path) -> None:
        """A credential that never reaches the compiled bundle — here in the
        ``PUBLISHABLE`` marker — is caught by the same scanner promotion uses."""
        sample = FAKE_CREDENTIALS["AWS access key id"]
        marker = promoted / "source" / "knowledge" / "gold" / "PUBLISHABLE"
        marker.write_text(marker.read_text(encoding="utf-8") + f"{sample}\n", encoding="utf-8")
        load_candidate_bundle(promoted)  # the bundle alone is still clean
        with pytest.raises(AssertionError) as info:
            check_secret_slot_names_only(promoted)
        assert "PUBLISHABLE" in str(info.value) and "AWS access key id" in str(info.value)
        assert sample not in str(info.value)

    def test_a_completed_promotion_passes_every_check(self, promoted: Path, tmp_path: Path) -> None:
        readme = promoted / "README.md"
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.DOTALL).replace(README_TODO_MARKER, "operator note")
        readme.write_text(text, encoding="utf-8")
        check_ingests_and_carries_its_hash(promoted)
        check_secret_slot_names_only(promoted)
        check_readme_is_complete(promoted)
        check_source_reexports_the_bundle(promoted, tmp_path)
        check_vendored_knowledge_is_declared_publishable(promoted)
