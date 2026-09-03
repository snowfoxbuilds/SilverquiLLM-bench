"""Candidate Bundle ingestion — the trust boundary for every published result.

Every bundle here is a real ``theozolith candidate export`` (fake digest
resolver, fixed timestamp; no registry, no Docker).  The tests pin that the
bench recomputes identity through TheOzolith's verifier and never trusts a
recorded value (tampered bundles, mismatched recorded identities, and a
mismatched ``<slug>--<hash8>`` directory name are hard refusals printing both
values), that a bundle carrying a secret VALUE is refused before the verifier
runs, that the published golden vectors reproduce through the bench's
ingestion, that no adapter allowlist exists on the bench side, that the
vendored results-repo copy is write-once and verified at write time, and that
the derived image is launched only under its own identity labels.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest
from theozolith_control import candidate as ozcandidate

from silverquillm import candidate as cand
from silverquillm.candidate import (
    BuiltImage,
    CandidateRefusedError,
    CandidateVendorError,
    ImageBuildError,
    build_candidate_image,
    load_candidate_bundle,
    vendor_candidate,
)
from silverquillm.contract_version import CONTRACT_IDENTITY_SPEC_VERSION
from silverquillm.results_repo import (
    OZOLITH_SCHEME,
    CandidateIdentity,
    candidate_copy_dir,
    candidate_hash,
    iter_run_dirs,
)
from tests.candidate_fixtures import (
    DIGEST_A,
    DIGEST_B,
    FAKE_ANTHROPIC_KEY,
    export_bundle,
    fake_image_builder,
    identity_of,
    make_candidate_dir,
    rewrite_manifest,
)

REPO = Path(__file__).resolve().parents[1]
VECTORS = REPO / "docs" / "specs" / "bench-identity-vectors.json"

#: The bench's candidate hash of the published ``claude-no-knowledge`` vector's
#: triple — a literal, so the key rule can never drift silently.
CLAUDE_NO_KNOWLEDGE_CANDIDATE_HASH = (
    "74e6198d8500024a1d8df060c9a2e6906011fc7dd6e5a23d7d4d66e194895f96"
)


class _Spy:
    """A verifier double that must never be reached (secret-value refusals
    precede verification) or that answers with a chosen identity."""

    def __init__(self, summary=None):
        self.calls: list[Path] = []
        self.summary = summary

    def __call__(self, bundle: Path):
        self.calls.append(Path(bundle))
        if self.summary is None:
            raise AssertionError("the verifier must not be reached")
        return self.summary


# ---------------------------------------------------------------------------
# Loading and identity
# ---------------------------------------------------------------------------


class TestLoadCandidateBundle:
    def test_identity_is_recomputed_through_the_verifier(self, tmp_path: Path) -> None:
        bundle_dir, summary = export_bundle(tmp_path)
        bundle = load_candidate_bundle(bundle_dir)
        assert bundle.path == bundle.bundle_path == bundle_dir
        assert bundle.identity == identity_of(summary)
        assert bundle.identity.scheme == OZOLITH_SCHEME and bundle.identity.verified is True
        assert bundle.base_digest == DIGEST_A == summary.base_digest
        assert bundle.instruction_hash == summary.instruction_hash
        assert bundle.adapter == "claude" and bundle.worker_type == "fixture-claude"
        assert bundle.tag == summary.tag
        assert bundle.model == "claude-sonnet-5" and bundle.effort == ""
        assert bundle.driver == "builtin:implementer"
        assert bundle.secret_slots == ("ANTHROPIC_API_KEY",)
        assert bundle.product_version == "0.3.0" and bundle.exported_at == "2026-09-03T00:00:00Z"
        assert bundle.bundle_format_version == 2 and bundle.identity_spec_version == 2
        # The bench's key: sha256 of the compact canonical triple.
        canonical = json.dumps(
            {"adapter": "claude", "base_digest": DIGEST_A, "instruction_hash": summary.instruction_hash},
            sort_keys=True, separators=(",", ":"),
        )
        assert bundle.candidate_hash == hashlib.sha256(canonical.encode()).hexdigest()
        assert bundle.hash8 == bundle.candidate_hash[:8]
        summary_dict = bundle.summary_dict()
        assert summary_dict["identity"] == bundle.identity.to_dict()
        assert summary_dict["secret_slots"] == ["ANTHROPIC_API_KEY"]

    def test_a_checked_in_candidate_directory_wraps_the_bundle(self, tmp_path: Path) -> None:
        candidate_dir = make_candidate_dir(tmp_path)
        assert re.fullmatch(r"fixture-claude--[0-9a-f]{8}", candidate_dir.name)
        bundle = load_candidate_bundle(candidate_dir)
        assert bundle.path == candidate_dir
        assert bundle.bundle_path == candidate_dir / "bundle"
        assert candidate_dir.name.endswith(bundle.hash8)
        assert (candidate_dir / "README.md").is_file()  # beside, never inside, the bundle

    def test_a_mismatched_directory_suffix_is_a_hard_refusal_printing_both(self, tmp_path: Path) -> None:
        candidate_dir = make_candidate_dir(tmp_path)
        bundle = load_candidate_bundle(candidate_dir)
        renamed = tmp_path / "fixture-claude--deadbeef"
        candidate_dir.rename(renamed)
        with pytest.raises(CandidateRefusedError) as refusal:
            load_candidate_bundle(renamed)
        message = str(refusal.value)
        assert "deadbeef" in message and bundle.hash8 in message and "never trusted" in message

    def test_not_a_bundle_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()
        with pytest.raises(CandidateRefusedError, match="not a Candidate Bundle"):
            load_candidate_bundle(tmp_path / "empty")
        with pytest.raises(CandidateRefusedError, match="not a directory"):
            load_candidate_bundle(tmp_path / "missing")

    def test_codex_bundle_ingests_with_its_own_adapter(self, tmp_path: Path) -> None:
        from tests.candidate_fixtures import CODEX_BASE

        bundle_dir, summary = export_bundle(
            tmp_path, name="fixture-codex", adapter="codex", model="gpt-5.2-codex",
            base=CODEX_BASE, secrets=("OPENAI_API_KEY",),
        )
        bundle = load_candidate_bundle(bundle_dir)
        assert bundle.adapter == "codex" and bundle.identity.adapter_identity == "codex"
        assert bundle.identity == identity_of(summary)


# ---------------------------------------------------------------------------
# Golden vectors
# ---------------------------------------------------------------------------


def _vectors() -> list[dict]:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data["identity_spec_version"] == CONTRACT_IDENTITY_SPEC_VERSION
    return data["vectors"]


class TestGoldenVectors:
    def test_vendored_vectors_are_the_pinned_revisions(self) -> None:
        """The vendored vectors file is the-ozolith's at the pinned revision:
        every vector must recompute through the installed verifier's own
        formula (the bench never reimplements it)."""
        from theozolith_control import configrepo

        vectors = _vectors()
        assert len(vectors) >= 5
        assert len({vector["fields"]["adapter"] for vector in vectors}) >= 2  # no adapter set hardcoded
        for vector in vectors:
            fields = vector["fields"]
            wt = configrepo.WorkerTypeDef(
                name=fields["name"], base=fields["base"], setup=tuple(fields["setup"]),
                knowledge=fields["knowledge"], knowledge_pin=fields["knowledge_pin"],
                policy=fields.get("policy", ""), policy_pin=fields.get("policy_pin", ""),
                driver=fields["driver"], adapter=fields["adapter"],
                model=fields["model"], effort=fields["effort"],
            )
            expected = vector["expected"]
            assert wt.instruction_hash == expected["instruction_hash"], vector["name"]
            assert hashlib.sha256(expected["canonical_identity"].encode()).hexdigest() == wt.instruction_hash
            assert expected["identity_triple"] == {
                "base_digest": wt.base_digest, "instruction_hash": wt.instruction_hash, "adapter": wt.adapter,
            }
            assert wt.tag == expected["tag"]

    def test_bench_key_over_every_vector_triple_is_deterministic_and_distinct(self) -> None:
        keys = {}
        for vector in _vectors():
            triple = vector["expected"]["identity_triple"]
            identity = CandidateIdentity.recomputed(
                triple["base_digest"], triple["instruction_hash"], triple["adapter"]
            )
            key = candidate_hash(identity)
            assert re.fullmatch(r"[0-9a-f]{64}", key)
            assert key == candidate_hash(identity)  # deterministic
            keys[vector["name"]] = key
        assert len(set(keys.values())) == len(keys)  # injective over the published vectors
        assert keys["claude-no-knowledge"] == CLAUDE_NO_KNOWLEDGE_CANDIDATE_HASH

    @pytest.mark.parametrize("name", ["claude-no-knowledge", "claude-model-effort"])
    def test_knowledge_free_vectors_reproduce_end_to_end_through_ingestion(self, tmp_path: Path, name: str) -> None:
        """Export a bundle from the vector's fields and ingest it: the bench
        attributes exactly the published identity triple and tag.  (The
        knowledge-bearing vectors pin compiled trees the vectors file does
        not ship, so they are covered by the formula test above.)"""
        [vector] = [v for v in _vectors() if v["name"] == name]
        fields, expected = vector["fields"], vector["expected"]
        bundle_dir, _ = export_bundle(
            tmp_path, name=fields["name"], adapter=fields["adapter"], model=fields["model"],
            effort=fields["effort"], driver=fields["driver"], base=fields["base"],
            setup=tuple(fields["setup"]), secrets=(),
        )
        bundle = load_candidate_bundle(bundle_dir)
        assert bundle.identity.to_dict() == {
            "scheme": OZOLITH_SCHEME,
            "base_image_digest": expected["identity_triple"]["base_digest"],
            "instruction_hash": expected["identity_triple"]["instruction_hash"],
            "adapter_identity": expected["identity_triple"]["adapter"],
            "verified": True,
        }
        assert bundle.tag == expected["tag"]
        assert json.loads((bundle_dir / "candidate.json").read_text())["setup"] == fields["setup"]


# ---------------------------------------------------------------------------
# Refusals: tampering, recorded-identity mismatch, secret values
# ---------------------------------------------------------------------------


class TestRefusals:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("instruction_hash", "f" * 64),
            ("base_digest", DIGEST_B),
            ("adapter", "codex"),
            ("model", "claude-opus-5"),
            ("setup", ["echo pwned"]),
        ],
    )
    def test_a_tampered_manifest_is_refused(self, tmp_path: Path, field: str, value) -> None:
        bundle_dir, _ = export_bundle(tmp_path)
        rewrite_manifest(bundle_dir, **{field: value})
        with pytest.raises(CandidateRefusedError, match="verification"):
            load_candidate_bundle(bundle_dir)

    def test_a_tampered_dockerfile_is_refused(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path)
        dockerfile = bundle_dir / "Dockerfile"
        dockerfile.write_text(dockerfile.read_text().replace("USER root", "USER root\nRUN echo pwned"))
        with pytest.raises(CandidateRefusedError, match="byte-match"):
            load_candidate_bundle(bundle_dir)

    def test_tampered_knowledge_bytes_and_unexpected_entries_are_refused(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        assert load_candidate_bundle(bundle_dir).knowledge == "knowledge/gold"
        target = bundle_dir / "knowledge" / "CLAUDE.md"
        original = target.read_bytes()
        target.write_bytes(original + b"\n<!-- tampered -->\n")
        with pytest.raises(CandidateRefusedError, match="pin"):
            load_candidate_bundle(bundle_dir)
        target.write_bytes(original)
        (bundle_dir / "extra.txt").write_text("smuggled")
        with pytest.raises(CandidateRefusedError, match="unexpected entries"):
            load_candidate_bundle(bundle_dir)

    def test_recorded_identity_disagreeing_with_the_recomputed_one_prints_both(self, tmp_path: Path) -> None:
        """The bench's own comparison: with a verifier answering a triple the
        manifest does not record, the refusal names both values."""
        bundle_dir, summary = export_bundle(tmp_path)
        forged = ozcandidate.CandidateSummary(
            worker_type=summary.worker_type, adapter=summary.adapter,
            base_digest=summary.base_digest, instruction_hash="c" * 64, tag=summary.tag,
        )
        with pytest.raises(CandidateRefusedError) as refusal:
            load_candidate_bundle(bundle_dir, verifier=_Spy(forged))
        message = str(refusal.value)
        assert summary.instruction_hash in message and "c" * 64 in message
        assert "never trusted" in message

    def test_a_secret_value_in_a_slot_entry_is_refused_before_verification(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path)
        rewrite_manifest(bundle_dir, secret_slots=[f"ANTHROPIC_API_KEY={FAKE_ANTHROPIC_KEY}"])
        spy = _Spy()
        with pytest.raises(CandidateRefusedError) as refusal:
            load_candidate_bundle(bundle_dir, verifier=spy)
        assert "environment-variable name" in str(refusal.value)
        assert FAKE_ANTHROPIC_KEY not in str(refusal.value)  # never echoed
        assert spy.calls == []

    def test_a_secret_value_carrier_field_is_refused_before_verification(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path)
        rewrite_manifest(bundle_dir, secrets={"ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY})
        spy = _Spy()
        with pytest.raises(CandidateRefusedError, match="secret-value carrier"):
            load_candidate_bundle(bundle_dir, verifier=spy)
        assert spy.calls == []

    @pytest.mark.parametrize(
        ("payload", "shape"),
        [
            (f"api key: {FAKE_ANTHROPIC_KEY}\n", "Anthropic API key"),
            ("token: ghp_" + "A" * 36 + "\n", "GitHub token"),
            ("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n", "private key block"),
            ("export ANTHROPIC_API_KEY=" + "k" * 32 + "\n", "a value assigned to secret slot ANTHROPIC_API_KEY"),
        ],
    )
    def test_a_credential_shaped_byte_anywhere_in_the_bundle_is_refused(
        self, tmp_path: Path, payload: str, shape: str
    ) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        planted = bundle_dir / "knowledge" / "CLAUDE.md"
        planted.write_text(planted.read_text() + "\n" + payload, encoding="utf-8")
        spy = _Spy()
        with pytest.raises(CandidateRefusedError) as refusal:
            load_candidate_bundle(bundle_dir, verifier=spy)
        message = str(refusal.value)
        assert shape in message and "knowledge/CLAUDE.md" in message
        assert payload.strip().split()[-1] not in message  # the value itself is never echoed
        assert spy.calls == []

    def test_a_slot_name_mentioned_in_docs_without_a_value_is_fine(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        doc = bundle_dir / "knowledge" / "CLAUDE.md"
        doc.write_text(doc.read_text() + "\nSet ANTHROPIC_API_KEY=<your key> before running.\n")
        spy = _Spy()
        with pytest.raises(CandidateRefusedError, match="pin"):  # the edit fails the pin, not the scan
            load_candidate_bundle(bundle_dir)
        # The scan itself passes the doc and reaches the verifier.
        with pytest.raises(AssertionError, match="must not be reached"):
            load_candidate_bundle(bundle_dir, verifier=spy)
        assert spy.calls == [bundle_dir]


# ---------------------------------------------------------------------------
# Adapter agnosticism
# ---------------------------------------------------------------------------


class TestNoAdapterAllowlist:
    def test_an_arbitrary_adapter_reaches_the_injected_verifier_without_a_bench_allowlist(
        self, tmp_path: Path
    ) -> None:
        """The bench layer imposes nothing on the adapter name: a structurally
        valid adapter token the bench has never heard of reaches the verifier
        untouched, and when the (injected) verifier answers for it, the
        identity, the key, and the manifest all carry it verbatim.  This says
        nothing about whether TheOzolith admits the adapter — that is the real
        verifier's call (next test), never a bench rule."""
        bundle_dir, summary = export_bundle(tmp_path)
        rewrite_manifest(bundle_dir, adapter="pi")
        pi = ozcandidate.CandidateSummary(
            worker_type=summary.worker_type, adapter="pi", base_digest=summary.base_digest,
            instruction_hash=summary.instruction_hash, tag=summary.tag,
        )
        bundle = load_candidate_bundle(bundle_dir, verifier=_Spy(pi))
        assert bundle.adapter == "pi" and bundle.identity.adapter_identity == "pi"
        assert bundle.candidate_hash != candidate_hash(identity_of(summary))  # adapter is key-bearing

    def test_which_adapters_exist_is_the_verifiers_gate_not_the_benchs(self, tmp_path: Path) -> None:
        """The REAL verifier: a bundle naming an adapter TheOzolith cannot
        materialize is refused by its parse gate — reported as a verification
        refusal, never a bench rule.  So the complete real path admits exactly
        the adapters TheOzolith admits, with no bench-side list in either
        direction."""
        bundle_dir, _ = export_bundle(tmp_path)
        rewrite_manifest(bundle_dir, adapter="pi")
        with pytest.raises(CandidateRefusedError, match="verification") as refusal:
            load_candidate_bundle(bundle_dir)
        assert "adapter" in str(refusal.value)

    def test_no_bench_module_hardcodes_the_adapter_set(self) -> None:
        pattern = re.compile(r"""[\[({]\s*["'](?:claude|codex)["']\s*,\s*["'](?:claude|codex)["']""")
        for module in ("candidate", "contract", "contract_record", "jobdir", "modes", "results_repo"):
            source = (REPO / "silverquillm" / f"{module}.py").read_text(encoding="utf-8")
            assert not pattern.search(source), f"{module}.py lists adapter names"


# ---------------------------------------------------------------------------
# The vendored copy in the results repo
# ---------------------------------------------------------------------------


class TestVendorCandidate:
    def test_written_once_verified_at_write_time_then_skipped(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        bundle = load_candidate_bundle(bundle_dir)
        repo = tmp_path / "results-repo"
        first = vendor_candidate(repo, bundle)
        assert first.written is True
        assert first.path == candidate_copy_dir(repo, bundle.identity)
        assert first.path.parent.name == bundle.candidate_hash
        assert sorted(p.name for p in first.path.iterdir()) == ["Dockerfile", "candidate.json", "knowledge"]
        # Byte-identical to the bundle, and it verifies on its own.
        for path in bundle_dir.rglob("*"):
            if path.is_file():
                assert (first.path / path.relative_to(bundle_dir)).read_bytes() == path.read_bytes()
        assert ozcandidate.verify_bundle(first.path).instruction_hash == bundle.instruction_hash
        assert not [p for p in first.path.parent.iterdir() if p.name.startswith(".")]  # no staging litter

        second = vendor_candidate(repo, bundle)
        assert second.written is False and second.path == first.path
        assert list(iter_run_dirs(repo)) == []  # the copy is never a run

    def test_a_tampered_existing_copy_is_refused_never_repaired(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        bundle = load_candidate_bundle(bundle_dir)
        repo = tmp_path / "results-repo"
        copy = vendor_candidate(repo, bundle).path
        knowledge = copy / "knowledge" / "CLAUDE.md"
        tampered = knowledge.read_bytes() + b"x"
        knowledge.write_bytes(tampered)
        with pytest.raises(CandidateVendorError, match="fails verification"):
            vendor_candidate(repo, bundle)
        assert knowledge.read_bytes() == tampered  # untouched

    def test_a_copy_of_another_candidate_under_this_hash_is_refused(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path)
        bundle = load_candidate_bundle(bundle_dir)
        other_dir, _ = export_bundle(tmp_path / "other", model="claude-opus-5")
        repo = tmp_path / "results-repo"
        target = candidate_copy_dir(repo, bundle.identity)
        target.parent.mkdir(parents=True)
        import shutil

        shutil.copytree(other_dir, target)  # a self-consistent bundle, but not this one
        with pytest.raises(CandidateVendorError, match="not the directory's"):
            vendor_candidate(repo, bundle)

    def test_a_symlink_planted_after_ingestion_is_refused_and_never_copied(self, tmp_path: Path) -> None:
        bundle_dir, _ = export_bundle(tmp_path, knowledge=True)
        bundle = load_candidate_bundle(bundle_dir)
        secret = tmp_path / "host-secret.txt"
        secret.write_text("outside the bundle")
        os.symlink(secret, bundle_dir / "knowledge" / "leak.md")
        repo = tmp_path / "results-repo"
        with pytest.raises(CandidateVendorError, match="symlink"):
            vendor_candidate(repo, bundle)
        assert not candidate_copy_dir(repo, bundle.identity).exists()
        assert not list((repo / "results").rglob("leak.md")) if (repo / "results").exists() else True


# ---------------------------------------------------------------------------
# The derived image
# ---------------------------------------------------------------------------


class TestBuildCandidateImage:
    def test_launches_by_id_after_checking_the_identity_labels(self, tmp_path: Path) -> None:
        bundle = load_candidate_bundle(export_bundle(tmp_path)[0])
        built: list[Path] = []

        def builder(path: Path) -> str:
            built.append(path)
            return bundle.tag

        def inspector(tag: str):
            assert tag == bundle.tag
            return "sha256:" + "1" * 64, {
                "theozolith.base-digest": bundle.base_digest,
                "theozolith.instruction-hash": bundle.instruction_hash,
            }

        image = build_candidate_image(bundle, builder=builder, inspector=inspector)
        assert image == BuiltImage(tag=bundle.tag, image_id="sha256:" + "1" * 64)
        assert built == [bundle.bundle_path]
        assert image.to_dict() == {"tag": bundle.tag, "id": "sha256:" + "1" * 64}

    def test_a_tag_naming_another_image_is_refused(self, tmp_path: Path) -> None:
        bundle = load_candidate_bundle(export_bundle(tmp_path)[0])
        def wrong(tag: str):
            return "sha256:" + "2" * 64, {"theozolith.instruction-hash": "f" * 64}

        with pytest.raises(ImageBuildError, match="does not name this candidate"):
            build_candidate_image(bundle, builder=lambda path: bundle.tag, inspector=wrong)

    def test_a_build_tagging_something_else_is_refused(self, tmp_path: Path) -> None:
        bundle = load_candidate_bundle(export_bundle(tmp_path)[0])
        with pytest.raises(ImageBuildError, match="deterministic tag"):
            build_candidate_image(bundle, builder=lambda path: "theozolith/other:1", inspector=lambda t: ("x", {}))

    def test_the_fixture_builder_double(self, tmp_path: Path) -> None:
        bundle = load_candidate_bundle(export_bundle(tmp_path)[0])
        assert fake_image_builder(bundle).tag == bundle.tag

    def test_the_real_build_is_the_verified_standalone_build(self) -> None:
        """Statically: the default builder is TheOzolith's ``build_candidate``
        (snapshot → verify → build → tag), never a raw ``docker build``."""
        source = (REPO / "silverquillm" / "candidate.py").read_text(encoding="utf-8")
        assert "ozcandidate.build_candidate(" in source
        assert '"docker", "build"' not in source and "docker build" not in source.replace("``docker build``", "")
        assert cand._verified_build is not None
