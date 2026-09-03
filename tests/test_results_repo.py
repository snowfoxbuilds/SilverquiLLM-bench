"""Tests for ``silverquillm/results_repo.py`` — the private results repo (#39 §3, #63).

Covers the schema (identity, ``RunRecord`` validation), the immutable atomic
writer, the single-owner ``leaderboard_valid`` rule with the real ``"1"`` vs
``"001"`` collector-number shapes, the derived index's determinism, the
``--results-repo`` / ``SILVERQUILLM_RESULTS_REPO`` resolution, and
``silverquillm results-init``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from silverquillm import results_repo as rr
from silverquillm.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SOS_CONFIG = json.loads((REPO_ROOT / "benchmarks" / "sos" / "config.json").read_text())
SMOKE_CONFIG = json.loads((REPO_ROOT / "benchmarks" / "smoke" / "config.json").read_text())

# The real legacy shapes: manifests store unpadded numbers, eval_result keys
# carry the set prefix, config.json zero-pads.
LEGACY_FILTER = ["1", "4", "13", "57", "97", "120", "201", "226", "245", "257"]
SCORED_SOS = [f"sos_{n}" for n in LEGACY_FILTER]

# Every image dir in the real Validated Results corpus.  All are already safe
# path segments; their candidate directory keys must never change.
REAL_CORPUS_IMAGES = [
    "cc-fable-5-bare-high-planned",
    "cc-fable-5-bare-medium-planned",
    "cc-fable-5-bare-xhigh-planned",
    "cc-opus-48-bare",
    "cc-opus-48-bare-high-planned",
    "cc-opus-48-bare-xhigh",
    "cc-opus-48-bare-xhigh-planned",
    "cc-opus-48-plan-tdd-v2-xhigh",
    "cc-opus-48-plan-tdd-xhigh",
    "cc-opus-48-single",
    "cc-opus-48-single-xhigh",
    "cc-opus-single",
    "cc-sonnet-46-bare-high-planned",
    "cc-sonnet-single",
    "copilot-claude-opus-4.6",
    "copilot-gpt-5.4",
    "copilot-gpt54-single",
    "copilot-gpt54-sonnet-reviewer",
    "copilot-sonnet-gpt54-reviewer",
    "copilot-sonnet-single",
]


def _scores() -> dict[str, Any]:
    return {
        "card_correctness": {
            "audited_pass_rate": 0.8193,
            "card_pass_rate": 0.3,
            "cards_completed": 10,
            "cards_no_output": 0,
            "cards_timed_out": 0,
        },
        "fdn_regression": {"fdn_test_pass_rate": 1.0, "fdn_card_pass_rate": 0.6364},
        "engine_regression": {"engine_test_pass_rate": 1.0, "engine_churn_lines": 216},
    }


def _record(**overrides: Any) -> rr.RunRecord:
    fields: dict[str, Any] = {
        "run_id": "sos-img-a-2026-06-01T00-00",
        "candidate": rr.CandidateIdentity.legacy("img-a"),
        "mode": "legacy",
        "benchmark": "sos",
        "budget_seconds": 360000,
        "leaderboard_valid": True,
        "resumed_from": None,
        "run_metadata": {"run_date": "2026-06-01T01:00:00Z"},
        "proposal_status": None,
        "scores": _scores(),
    }
    fields.update(overrides)
    if "artifact_pointers" not in fields:
        # The canonical identity-bound pointer for whatever run_id/candidate
        # the test chose; deliberately-broken fields get no pointer at all.
        try:
            location = rr.legacy_tree_location(
                rr.legacy_image_dir(fields["candidate"]), fields["run_id"]
            )
            fields["artifact_pointers"] = [{"kind": rr.LEGACY_TREE_KIND, "location": location}]
        except (rr.ResultsRepoError, AttributeError):
            fields["artifact_pointers"] = []
    return rr.RunRecord(**fields)


def _legacy_dict(**overrides: Any) -> dict[str, Any]:
    """A well-formed persisted legacy identity, as the writer emits it."""
    data: dict[str, Any] = {
        "scheme": "legacy",
        "base_image_digest": "legacy:img-a",
        "instruction_hash": "legacy:img-a",
        "adapter_identity": "legacy:img-a",
        "verified": False,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestCandidateIdentity:
    def test_legacy_identity_carries_the_image_dir_in_every_hash_field(self) -> None:
        ident = rr.CandidateIdentity.legacy("cc-opus-48-bare")
        assert ident.scheme == rr.LEGACY_SCHEME
        assert ident.base_image_digest == "legacy:cc-opus-48-bare"
        assert ident.instruction_hash == "legacy:cc-opus-48-bare"
        assert ident.adapter_identity == "legacy:cc-opus-48-bare"

    def test_verified_is_false_from_construction_and_deserialization(self) -> None:
        assert rr.CandidateIdentity.legacy("x").verified is False
        assert rr.CandidateIdentity.from_dict(_legacy_dict()).verified is False

    def test_candidate_hash_is_the_image_dir_unchanged(self) -> None:
        assert (
            rr.candidate_hash(rr.CandidateIdentity.legacy("copilot-gpt-5.4")) == "copilot-gpt-5.4"
        )
        assert rr.candidate_hash(rr.CandidateIdentity.legacy("odd_name_")) == "odd_name_"

    def test_legacy_image_dir_round_trips(self) -> None:
        assert rr.legacy_image_dir(rr.CandidateIdentity.legacy("img-b")) == "img-b"

    def test_ozolith_hash_is_the_sha256_of_the_canonical_triple(self) -> None:
        """The ``ozolith-v1`` key hashes the WHOLE triple (adapter included —
        TheOzolith's canonical identity omits the adapter name, so the
        instruction hash alone is not injective over the identity)."""
        ident = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "claude")
        assert rr.legacy_image_dir(ident) is None
        canonical = json.dumps(
            {"adapter": "claude", "base_digest": "sha256:" + "a" * 64, "instruction_hash": "b" * 64},
            sort_keys=True, separators=(",", ":"),
        )
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert rr.candidate_hash(ident) == expected
        assert rr.candidate_hash8(ident) == expected[:8]
        assert rr.candidate_dirname("vanilla-claude", ident) == f"vanilla-claude--{expected[:8]}"
        # Adapter-injective: same base + instruction hash, different adapter, different key.
        twin = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "pi")
        assert rr.candidate_hash(twin) != expected
        assert rr.candidate_copy_dir(Path("/repo"), ident) == Path("/repo/results") / expected / "candidate"

    def test_candidate_dirname_rejects_unsafe_slugs(self) -> None:
        ident = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "claude")
        for bad in ("", ".hidden", "a b", "slug--with", "a/b"):
            with pytest.raises(rr.InvalidRunRecordError, match="slug"):
                rr.candidate_dirname(bad, ident)

    def test_legacy_identity_has_no_vendored_copy(self) -> None:
        with pytest.raises(rr.ResultsRepoError, match="vendored"):
            rr.candidate_copy_dir(Path("/repo"), rr.CandidateIdentity.legacy("img-a"))

    @pytest.mark.parametrize("bad", ["", ".", "..", "a/b"])
    def test_legacy_rejects_unsafe_image_dirs(self, bad: str) -> None:
        with pytest.raises(rr.InvalidRunRecordError):
            rr.CandidateIdentity.legacy(bad)

    @pytest.mark.parametrize("bad", [".hidden", "a b", "odd name!", "café", "a\tb", "a/../b"])
    def test_names_needing_sanitization_are_rejected_not_rewritten(self, bad: str) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="never sanitized"):
            rr.CandidateIdentity.legacy(bad)

    def test_formerly_colliding_names_cannot_share_a_directory(self) -> None:
        # Under the retired underscore sanitization both would have keyed
        # results/odd_name_/ — now only the already-safe spelling exists.
        with pytest.raises(rr.InvalidRunRecordError):
            rr.CandidateIdentity.legacy("odd name!")
        with pytest.raises(rr.InvalidRunRecordError):
            rr.CandidateIdentity.legacy("odd?name!")
        assert rr.candidate_hash(rr.CandidateIdentity.legacy("odd_name_")) == "odd_name_"

    def test_all_20_real_corpus_image_names_stay_accepted_and_unchanged(self) -> None:
        assert len(REAL_CORPUS_IMAGES) == 20
        for name in REAL_CORPUS_IMAGES:
            assert rr.candidate_hash(rr.CandidateIdentity.legacy(name)) == name
        live = (
            sorted(p.parent.name for p in (REPO_ROOT / "docker").glob("*/validated_results"))
            if (REPO_ROOT / "docker").is_dir()
            else []
        )
        if live:  # the legacy trees survive until #66; while they do, pin the list
            assert live == REAL_CORPUS_IMAGES

    @pytest.mark.parametrize("bad", ["img-a", ["legacy:img-a"], 7, None])
    def test_non_object_candidate_data_is_rejected(self, bad: Any) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="JSON object"):
            rr.CandidateIdentity.from_dict(bad)

    def test_dict_round_trip(self) -> None:
        ident = rr.CandidateIdentity.legacy("img-c")
        assert rr.CandidateIdentity.from_dict(ident.to_dict()) == ident

    @pytest.mark.parametrize("verified", [True, "false", "true", 1, 0, None])
    def test_a_legacy_identity_records_verified_as_the_literal_false(self, verified: Any) -> None:
        """Legacy provenance: a label, never verified — so ``verified`` must be
        the literal ``false``, never coerced (the ``ozolith-v1`` counterpart,
        the literal ``true``, is proven below)."""
        with pytest.raises(rr.InvalidRunRecordError, match="verified"):
            rr.CandidateIdentity.from_dict(_legacy_dict(verified=verified))

    def test_missing_verified_is_rejected_not_defaulted(self) -> None:
        data = _legacy_dict()
        del data["verified"]
        with pytest.raises(rr.InvalidRunRecordError, match="verified"):
            rr.CandidateIdentity.from_dict(data)

    @pytest.mark.parametrize(
        "key", ["scheme", "base_image_digest", "instruction_hash", "adapter_identity"]
    )
    def test_missing_identity_field_is_rejected(self, key: str) -> None:
        data = _legacy_dict()
        del data[key]
        with pytest.raises(rr.InvalidRunRecordError, match=key):
            rr.CandidateIdentity.from_dict(data)

    @pytest.mark.parametrize("value", [7, None, "", ["legacy:img-a"]])
    def test_identity_fields_are_never_coerced(self, value: Any) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="base_image_digest"):
            rr.CandidateIdentity.from_dict(_legacy_dict(base_image_digest=value))
        with pytest.raises(rr.InvalidRunRecordError, match="scheme"):
            rr.CandidateIdentity.from_dict(_legacy_dict(scheme=value))

    def test_mismatched_legacy_tokens_are_rejected(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="disagree"):
            rr.CandidateIdentity.from_dict(_legacy_dict(instruction_hash="legacy:img-b"))
        with pytest.raises(rr.InvalidRunRecordError, match="disagree"):
            rr.CandidateIdentity.from_dict(_legacy_dict(adapter_identity="legacy:img-b"))

    def test_legacy_fields_must_carry_the_token_shape(self) -> None:
        bare = {k: "img-a" for k in ("base_image_digest", "instruction_hash", "adapter_identity")}
        with pytest.raises(rr.InvalidRunRecordError, match="legacy:<image-dir>"):
            rr.CandidateIdentity.from_dict(_legacy_dict(**bare))
        hashes = ("base_image_digest", "instruction_hash", "adapter_identity")
        empty = {k: "legacy:" for k in hashes}
        with pytest.raises(rr.InvalidRunRecordError, match="legacy:<image-dir>"):
            rr.CandidateIdentity.from_dict(_legacy_dict(**empty))

    def test_unknown_scheme_is_rejected(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="unknown candidate identity scheme"):
            rr.CandidateIdentity.from_dict(_legacy_dict(scheme="sha-magic"))

    def test_ozolith_identity_deserializes_only_verified_and_well_shaped(self) -> None:
        """An ``ozolith-v1`` identity exists only as the verifier's output:
        it records ``verified: true``, and an unverified one — or one whose
        triple is not digest / 64-hex / safe-token shaped — is malformed."""
        data = {
            "scheme": rr.OZOLITH_SCHEME,
            "base_image_digest": "sha256:" + "a" * 64,
            "instruction_hash": "b" * 64,
            "adapter_identity": "claude",
            "verified": True,
        }
        ident = rr.CandidateIdentity.from_dict(data)
        assert ident.verified is True
        assert ident == rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "claude")
        with pytest.raises(rr.InvalidRunRecordError, match="verified"):
            rr.CandidateIdentity.from_dict({**data, "verified": False})
        with pytest.raises(rr.InvalidRunRecordError, match="base_image_digest"):
            rr.CandidateIdentity.from_dict({**data, "base_image_digest": "sha256:abc"})
        with pytest.raises(rr.InvalidRunRecordError, match="instruction_hash"):
            rr.CandidateIdentity.from_dict({**data, "instruction_hash": "h"})
        with pytest.raises(rr.InvalidRunRecordError, match="adapter_identity"):
            rr.CandidateIdentity.from_dict({**data, "adapter_identity": "a b"})
        # Any adapter TOKEN is admissible — the bench keeps no adapter allowlist.
        assert rr.CandidateIdentity.from_dict({**data, "adapter_identity": "pi"}).adapter_identity == "pi"

    def test_verified_ozolith_identity_round_trips_through_a_record(self, tmp_path: Path) -> None:
        ident = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "codex")
        run_dir = rr.write_run_record(tmp_path, _record(candidate=ident, artifact_pointers=[]))
        assert run_dir.parent.name == rr.candidate_hash(ident)
        record = rr.read_run_record(run_dir)
        assert record.candidate == ident and record.candidate.verified is True

    def test_vendored_candidate_entry_is_never_iterated_as_a_run(self, tmp_path: Path) -> None:
        ident = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "codex")
        run_dir = rr.write_run_record(tmp_path, _record(candidate=ident, artifact_pointers=[]))
        copy = rr.candidate_copy_dir(tmp_path, ident)
        copy.mkdir()
        (copy / "manifest.json").write_text("{}")  # a decoy: still never a run
        assert list(rr.iter_run_dirs(tmp_path)) == [run_dir]


# ---------------------------------------------------------------------------
# RunRecord validation
# ---------------------------------------------------------------------------


class TestRunRecordValidation:
    def test_well_formed_record_validates(self) -> None:
        _record().validate()

    def test_scores_must_have_exactly_the_neutral_keys(self) -> None:
        missing = _scores()
        del missing["engine_regression"]
        with pytest.raises(rr.InvalidRunRecordError, match="exactly the keys"):
            _record(scores=missing).validate()
        sos_specific = {**_scores(), "sos_card_correctness": {}}
        with pytest.raises(rr.InvalidRunRecordError, match="exactly the keys"):
            _record(scores=sos_specific).validate()

    def test_workload_is_rejected_as_retired_vocabulary(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="retired"):
            _record(run_metadata={"workload": "sos-subset"}).validate()

    @pytest.mark.parametrize("bad", ["", ".", "..", ".hidden", "a/b", "a b"])
    def test_run_id_must_be_one_safe_path_segment(self, bad: str) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="run_id"):
            _record(run_id=bad).validate()

    def test_pointer_needs_kind_and_location(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError, match="location"):
            _record(artifact_pointers=[{"kind": "legacy-tree"}]).validate()

    def test_budget_must_be_a_real_int(self) -> None:
        with pytest.raises(rr.InvalidRunRecordError):
            _record(budget_seconds=True).validate()
        with pytest.raises(rr.InvalidRunRecordError):
            _record(budget_seconds=-1).validate()


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


class TestWriteRunRecord:
    def test_layout_and_manifest_shape(self, tmp_path: Path) -> None:
        record = _record()
        run_dir = rr.write_run_record(tmp_path, record)

        assert run_dir == tmp_path / "results" / "img-a" / record.run_id
        manifest = json.loads((run_dir / "manifest.json").read_text())
        scores = json.loads((run_dir / "scores.json").read_text())

        assert manifest["schema_version"] == 1
        assert manifest["benchmark"] == "sos"
        assert "workload" not in manifest
        assert manifest["leaderboard_valid"] is True
        assert manifest["candidate"]["verified"] is False
        assert manifest["candidate_hash"] == run_dir.parent.name
        assert manifest["mode"] == "legacy"
        assert manifest["proposal_status"] is None
        assert manifest["artifact_pointers"] == record.artifact_pointers
        assert set(scores) == set(rr.SCORE_DIMENSIONS)
        assert scores["card_correctness"] == _scores()["card_correctness"]

    def test_refuses_overwrite_and_keeps_the_original(self, tmp_path: Path) -> None:
        first = _record()
        run_dir = rr.write_run_record(tmp_path, first)
        before = (run_dir / "scores.json").read_bytes()

        second = _record(scores={**_scores(), "engine_regression": {"engine_test_pass_rate": 0.0}})
        with pytest.raises(rr.RunRecordExistsError):
            rr.write_run_record(tmp_path, second)

        assert (run_dir / "scores.json").read_bytes() == before
        assert [p.name for p in run_dir.parent.iterdir()] == [first.run_id]  # no temp litter

    def test_serialization_failure_leaves_nothing_behind(self, tmp_path: Path) -> None:
        bad = _record(scores={**_scores(), "engine_regression": {"unserializable": {1, 2}}})
        with pytest.raises(TypeError):
            rr.write_run_record(tmp_path, bad)
        assert not (tmp_path / "results").exists()

    def test_lost_rename_race_is_reported_as_exists_and_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(self: Path, target: Any) -> Path:
            raise OSError("Directory not empty")

        monkeypatch.setattr(pathlib.Path, "rename", _boom)
        with pytest.raises(rr.RunRecordExistsError):
            rr.write_run_record(tmp_path, _record())
        candidate_dir = tmp_path / "results" / "img-a"
        assert list(candidate_dir.iterdir()) == []

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        a = rr.write_run_record(tmp_path / "one", _record())
        b = rr.write_run_record(tmp_path / "two", _record())
        for name in ("manifest.json", "scores.json"):
            assert (a / name).read_bytes() == (b / name).read_bytes()

    def test_read_round_trip(self, tmp_path: Path) -> None:
        record = _record(resumed_from="prior-run", leaderboard_valid=False)
        run_dir = rr.write_run_record(tmp_path, record)
        assert rr.read_run_record(run_dir) == record

    def test_smoke_record_has_the_same_shape_as_a_migrated_sos_record(self, tmp_path: Path) -> None:
        """The #64 driver writes ``benchmark: "smoke"`` records with the same writer."""
        smoke = _record(
            run_id="smoke-vanilla-claude-2026-09-02T10-00",
            candidate=rr.CandidateIdentity.legacy("vanilla-claude"),
            mode="basic",
            benchmark="smoke",
            leaderboard_valid=False,
            proposal_status="applied",
            artifact_pointers=[],
        )
        sos_dir = rr.write_run_record(tmp_path, _record())
        smoke_dir = rr.write_run_record(tmp_path, smoke)
        sos_scores = json.loads((sos_dir / "scores.json").read_text())
        smoke_scores = json.loads((smoke_dir / "scores.json").read_text())
        assert set(sos_scores) == set(smoke_scores) == set(rr.SCORE_DIMENSIONS)
        manifest = json.loads((smoke_dir / "manifest.json").read_text())
        assert manifest["benchmark"] == "smoke"
        assert manifest["proposal_status"] == "applied"
        assert manifest["leaderboard_valid"] is False

    def test_read_rejects_a_manifest_carrying_workload(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["workload"] = "sos"
        manifest_path.write_text(json.dumps(manifest))
        with pytest.raises(rr.InvalidRunRecordError, match="workload"):
            rr.read_run_record(run_dir)

    def test_write_rejects_a_verified_identity(self, tmp_path: Path) -> None:
        forged = dataclasses.replace(rr.CandidateIdentity.legacy("img-a"), verified=True)
        with pytest.raises(rr.InvalidRunRecordError, match="never verified"):
            rr.write_run_record(tmp_path, _record(candidate=forged))
        assert not (tmp_path / "results").exists()

    def test_write_rejects_mismatched_legacy_tokens(self, tmp_path: Path) -> None:
        forged = rr.CandidateIdentity(
            base_image_digest="legacy:img-a",
            instruction_hash="legacy:img-b",
            adapter_identity="legacy:img-a",
            scheme=rr.LEGACY_SCHEME,
        )
        with pytest.raises(rr.InvalidRunRecordError, match="disagree"):
            rr.write_run_record(tmp_path, _record(candidate=forged))
        assert not (tmp_path / "results").exists()

    def test_anything_the_writer_accepts_reads_straight_back(self, tmp_path: Path) -> None:
        variants = [
            _record(),
            _record(run_id="resumed-leg", resumed_from="prior-leg", leaderboard_valid=False),
            _record(
                run_id="smoke-vanilla-claude-2026-09-02T10-00",
                candidate=rr.CandidateIdentity.legacy("vanilla-claude"),
                mode="basic",
                benchmark="smoke",
                proposal_status="applied",
                leaderboard_valid=False,
                artifact_pointers=[],
            ),
        ]
        for record in variants:
            run_dir = rr.write_run_record(tmp_path, record)
            assert rr.read_run_record(run_dir) == record


# ---------------------------------------------------------------------------
# Read-time consistency — path, run id, identity, and hash must agree
# ---------------------------------------------------------------------------


class TestReadConsistency:
    """Every read must re-prove path ↔ manifest ↔ identity agreement."""

    def _edit_manifest(self, run_dir: Path, mutate: Any) -> None:
        path = run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        mutate(manifest)
        path.write_text(json.dumps(manifest))

    def test_run_id_must_match_the_directory_name(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        moved = run_dir.parent / "some-other-run"
        run_dir.rename(moved)
        with pytest.raises(rr.InvalidRunRecordError, match="does not match the directory name"):
            rr.read_run_record(moved)

    def test_manifest_candidate_hash_must_match_the_identity(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._edit_manifest(run_dir, lambda m: m.update(candidate_hash="img-evil"))
        with pytest.raises(rr.InvalidRunRecordError, match="candidate_hash 'img-evil'"):
            rr.read_run_record(run_dir)

    @pytest.mark.parametrize("bad", [None, 7, ""])
    def test_manifest_candidate_hash_must_be_a_non_empty_string(
        self, tmp_path: Path, bad: Any
    ) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._edit_manifest(run_dir, lambda m: m.update(candidate_hash=bad))
        with pytest.raises(rr.InvalidRunRecordError, match="candidate_hash"):
            rr.read_run_record(run_dir)

    def test_record_must_sit_under_its_candidate_directory(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        other = tmp_path / "results" / "img-other"
        other.mkdir()
        moved = other / run_dir.name
        run_dir.rename(moved)
        with pytest.raises(rr.InvalidRunRecordError, match="candidate's directory"):
            rr.read_run_record(moved)

    def test_persisted_verified_true_is_rejected_on_read(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._edit_manifest(run_dir, lambda m: m["candidate"].update(verified=True))
        with pytest.raises(rr.InvalidRunRecordError, match="never verified"):
            rr.read_run_record(run_dir)

    def test_iteration_and_the_index_fail_loudly_and_keep_the_old_index(
        self, tmp_path: Path
    ) -> None:
        rr.write_run_record(tmp_path, _record(run_id="run-b"))
        rr.write_run_record(tmp_path, _record())  # iterates after run-b
        rr.rebuild_index(tmp_path)
        before = (tmp_path / "runs.jsonl").read_bytes()
        assert before.count(b"\n") == 2
        tampered = tmp_path / "results" / "img-a" / _record().run_id
        self._edit_manifest(tampered, lambda m: m.update(candidate_hash="img-evil"))
        with pytest.raises(rr.InvalidRunRecordError):
            list(rr.iter_run_records(tmp_path))
        with pytest.raises(rr.InvalidRunRecordError):
            rr.rebuild_index(tmp_path)
        assert (tmp_path / "runs.jsonl").read_bytes() == before  # not truncated or replaced


# ---------------------------------------------------------------------------
# Strict deserialization — every field required, exact JSON types, no coercion
# ---------------------------------------------------------------------------


class TestStrictManifestDeserialization:
    """Malformed persisted data raises :class:`InvalidRunRecordError`, never a
    leaked ``AttributeError``/``TypeError``/``KeyError``, and is never
    normalized with ``str()``/``dict()``/``list()``/truthiness."""

    def _tamper(self, run_dir: Path, mutate: Any) -> None:
        path = run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        mutate(manifest)
        path.write_text(json.dumps(manifest))

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "run_id",
            "candidate",
            "candidate_hash",
            "mode",
            "benchmark",
            "budget_seconds",
            "leaderboard_valid",
            "resumed_from",
            "proposal_status",
            "run_metadata",
            "artifact_pointers",
        ],
    )
    def test_every_manifest_field_is_required_individually(
        self, tmp_path: Path, field: str
    ) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._tamper(run_dir, lambda m: m.pop(field))
        with pytest.raises(rr.InvalidRunRecordError, match=f"manifest lacks.*{field}"):
            rr.read_run_record(run_dir)

    @pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
    def test_schema_version_must_be_the_integer_1(self, tmp_path: Path, bad: Any) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._tamper(run_dir, lambda m: m.update(schema_version=bad))
        with pytest.raises(rr.InvalidRunRecordError, match="schema_version"):
            rr.read_run_record(run_dir)

    @pytest.mark.parametrize(
        ("field", "bad"),
        [
            ("run_metadata", [["run_date", "2026-06-01"]]),  # dict()-coercible pair list
            ("run_metadata", []),
            ("artifact_pointers", "docker/img-a/validated_results/x/"),  # list()-coercible
            ("artifact_pointers", {}),
            ("candidate", "img-a"),  # .get() would raise AttributeError
            ("candidate", ["legacy:img-a"]),
            ("budget_seconds", "360000"),  # int()-coercible
            ("leaderboard_valid", "true"),  # truthy
            ("mode", 7),  # str()-coercible
        ],
    )
    def test_coercible_but_wrong_json_shapes_are_rejected(
        self, tmp_path: Path, field: str, bad: Any
    ) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        self._tamper(run_dir, lambda m: m.update({field: bad}))
        with pytest.raises(rr.InvalidRunRecordError):
            rr.read_run_record(run_dir)

    def test_scores_file_must_be_an_object(self, tmp_path: Path) -> None:
        run_dir = rr.write_run_record(tmp_path, _record())
        (run_dir / "scores.json").write_text("[1, 2]")
        with pytest.raises(rr.InvalidRunRecordError, match="objects"):
            rr.read_run_record(run_dir)

    def test_from_dicts_rejects_non_mapping_inputs(self) -> None:
        record = _record()
        with pytest.raises(rr.InvalidRunRecordError, match="manifest must be a JSON object"):
            rr.RunRecord.from_dicts("not a mapping", record.scores_dict())
        with pytest.raises(rr.InvalidRunRecordError, match="scores must be a JSON object"):
            rr.RunRecord.from_dicts(record.manifest_dict(), [1, 2])


# ---------------------------------------------------------------------------
# legacy-tree pointers — identity-bound to the canonical location
# ---------------------------------------------------------------------------


class TestLegacyTreePointerBinding:
    """A ``legacy-tree`` pointer must be exactly the canonical path for the
    record's own candidate and run id — never another candidate's artifacts."""

    def test_the_canonical_location_helper(self) -> None:
        assert rr.legacy_tree_location("img-a", "run-1") == "docker/img-a/validated_results/run-1/"
        with pytest.raises(rr.InvalidRunRecordError, match="image dir"):
            rr.legacy_tree_location("img/../a", "run-1")
        with pytest.raises(rr.InvalidRunRecordError, match="run id"):
            rr.legacy_tree_location("img-a", "../run-1")

    def test_the_default_record_carries_the_canonical_pointer(self) -> None:
        record = _record()
        assert record.artifact_pointers == [
            {
                "kind": "legacy-tree",
                "location": "docker/img-a/validated_results/sos-img-a-2026-06-01T00-00/",
            }
        ]
        record.validate()

    @pytest.mark.parametrize(
        "location",
        [
            "/docker/img-a/validated_results/sos-img-a-2026-06-01T00-00/",  # absolute
            "/etc/passwd",  # absolute, elsewhere entirely
            "docker/../secrets/validated_results/sos-img-a-2026-06-01T00-00/",  # traversal
            "docker/img-a/validated_results/../sos-img-a-2026-06-01T00-00/",  # traversal
            "docker/img-b/validated_results/sos-img-a-2026-06-01T00-00/",  # another image
            "docker/img-a/validated_results/other-run/",  # another run
            "docker/img-a/validated_results/sos-img-a-2026-06-01T00-00",  # no trailing slash
            "./docker/img-a/validated_results/sos-img-a-2026-06-01T00-00/",  # dot spelling
        ],
    )
    def test_non_canonical_locations_are_rejected(self, location: str) -> None:
        record = _record(artifact_pointers=[{"kind": rr.LEGACY_TREE_KIND, "location": location}])
        with pytest.raises(rr.InvalidRunRecordError, match="canonical"):
            record.validate()

    def test_swapping_the_pointer_to_another_run_is_rejected_on_read(
        self, tmp_path: Path
    ) -> None:
        a = _record()
        b = _record(run_id="sos-img-a-2026-06-02T00-00")
        rr.write_run_record(tmp_path, b)
        run_dir = rr.write_run_record(tmp_path, a)
        path = run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["artifact_pointers"][0]["location"] = b.artifact_pointers[0]["location"]
        path.write_text(json.dumps(manifest))
        with pytest.raises(rr.InvalidRunRecordError, match="canonical"):
            rr.read_run_record(run_dir)

    def test_duplicate_legacy_tree_pointers_are_rejected(self) -> None:
        good = _record().artifact_pointers[0]
        record = _record(artifact_pointers=[dict(good), dict(good)])
        with pytest.raises(rr.InvalidRunRecordError, match="duplicate"):
            record.validate()

    def test_a_legacy_tree_pointer_requires_a_legacy_identity(self) -> None:
        ident = rr.CandidateIdentity.recomputed("sha256:" + "a" * 64, "b" * 64, "claude")
        record = _record(
            candidate=ident,
            artifact_pointers=[
                {"kind": rr.LEGACY_TREE_KIND, "location": "docker/x/validated_results/y/"}
            ],
        )
        with pytest.raises(rr.InvalidRunRecordError, match="legacy candidate identity"):
            record.validate()

    def test_records_without_a_legacy_tree_pointer_stay_valid(self) -> None:
        _record(artifact_pointers=[]).validate()
        _record(
            artifact_pointers=[{"kind": "artifact-host", "location": "s3://bucket/run"}]
        ).validate()


# ---------------------------------------------------------------------------
# leaderboard_valid
# ---------------------------------------------------------------------------


class TestDeriveLeaderboardValid:
    def test_unpadded_legacy_filter_equals_the_padded_config_set(self) -> None:
        assert rr.derive_leaderboard_valid(SOS_CONFIG, LEGACY_FILTER, None, SCORED_SOS) is True

    def test_padded_filter_and_bare_scored_numbers_are_the_same_cards(self) -> None:
        assert (
            rr.derive_leaderboard_valid(SOS_CONFIG, SOS_CONFIG["cards"], None, LEGACY_FILTER)
            is True
        )

    def test_no_filter_with_the_full_scored_set_is_valid(self) -> None:
        assert rr.derive_leaderboard_valid(SOS_CONFIG, None, None, SCORED_SOS) is True

    def test_narrower_filter_is_invalid(self) -> None:
        reasons = rr.leaderboard_validity_reasons(
            SOS_CONFIG, LEGACY_FILTER[:3], None, SCORED_SOS[:3]
        )
        assert any("card filter" in r for r in reasons)
        assert (
            rr.derive_leaderboard_valid(SOS_CONFIG, LEGACY_FILTER[:3], None, SCORED_SOS[:3])
            is False
        )

    def test_resume_leg_is_invalid(self) -> None:
        reasons = rr.leaderboard_validity_reasons(
            SOS_CONFIG, LEGACY_FILTER, "prior-leg", SCORED_SOS
        )
        assert reasons == ["Resume Leg (resumed_from=prior-leg)"]

    def test_ineligible_benchmark_is_invalid_even_when_sets_match(self) -> None:
        assert SMOKE_CONFIG["leaderboard"]["eligible"] is False
        scored = [f"fdn_{n}" for n in SMOKE_CONFIG["cards"]]
        reasons = rr.leaderboard_validity_reasons(SMOKE_CONFIG, SMOKE_CONFIG["cards"], None, scored)
        assert reasons == ["benchmark is not leaderboard-eligible (leaderboard.eligible: false)"]

    def test_eligible_defaults_to_true_when_absent(self) -> None:
        assert "eligible" not in SOS_CONFIG["leaderboard"]
        assert rr.derive_leaderboard_valid(SOS_CONFIG, None, None, SCORED_SOS) is True

    def test_pre_audited_set_271_card_run_is_invalid(self) -> None:
        scored = [f"sos_{n}" for n in range(1, 272)]
        reasons = rr.leaderboard_validity_reasons(SOS_CONFIG, None, None, scored)
        assert reasons == ["scored card set (271 cards) differs from the benchmark's 10-card set"]

    def test_empty_pool_never_validates(self) -> None:
        config = {"cards": [], "leaderboard": {}}
        assert rr.derive_leaderboard_valid(config, None, None, ["sos_1"]) is False

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("001", "1"),
            ("1", "1"),
            ("sos_001", "1"),
            ("sos_1", "1"),
            (7, "7"),
            ("fdn_129", "129"),
            ("12a", "12a"),
            (" 004 ", "4"),
        ],
    )
    def test_normalize_collector_number(self, raw: str | int, expected: str) -> None:
        assert rr.normalize_collector_number(raw) == expected


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestResolveResultsRepo:
    def test_flag_wins_over_env(self) -> None:
        env = {rr.RESULTS_REPO_ENV: "/from/env"}
        assert rr.resolve_results_repo("/from/flag", env) == Path("/from/flag")

    def test_env_used_when_flag_absent(self) -> None:
        assert rr.resolve_results_repo(None, {rr.RESULTS_REPO_ENV: "/from/env"}) == Path(
            "/from/env"
        )

    def test_absent_means_feature_off(self) -> None:
        assert rr.resolve_results_repo(None, {}) is None
        assert rr.resolve_results_repo(None, {rr.RESULTS_REPO_ENV: "  "}) is None

    def test_reads_the_process_environment_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(rr.RESULTS_REPO_ENV, "/proc/env")
        assert rr.resolve_results_repo(None) == Path("/proc/env")
        monkeypatch.delenv(rr.RESULTS_REPO_ENV)
        assert rr.resolve_results_repo(None) is None


class TestLoadBenchmarkConfig:
    def test_loads_the_real_sos_config(self) -> None:
        assert rr.load_benchmark_config(REPO_ROOT, "sos")["id"] == "sos"

    def test_missing_benchmark_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(rr.ResultsRepoError, match="no benchmark config"):
            rr.load_benchmark_config(tmp_path, "nope")

    def test_unsafe_id_is_rejected(self) -> None:
        with pytest.raises(rr.ResultsRepoError, match="invalid benchmark id"):
            rr.load_benchmark_config(REPO_ROOT, "../sos")


# ---------------------------------------------------------------------------
# Derived index
# ---------------------------------------------------------------------------


class TestRebuildIndex:
    def _populate(self, repo: Path) -> None:
        # Written out of order on purpose: the index must not depend on it.
        rr.write_run_record(
            repo, _record(run_id="run-b", candidate=rr.CandidateIdentity.legacy("img-z"))
        )
        rr.write_run_record(repo, _record(run_id="run-c"))
        rr.write_run_record(
            repo,
            _record(
                run_id="run-a",
                leaderboard_valid=False,
                run_metadata={"run_date": "2026-05-01T00:00:00Z"},
            ),
        )

    def test_rows_are_sorted_and_carry_the_documented_fields(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        rows = rr.rebuild_index(tmp_path)
        assert [(r["candidate_hash"], r["run_id"]) for r in rows] == [
            ("img-a", "run-a"),
            ("img-a", "run-c"),
            ("img-z", "run-b"),
        ]
        assert set(rows[0]) == {
            "candidate_hash",
            "run_id",
            "benchmark",
            "mode",
            "leaderboard_valid",
            "run_date",
        }
        assert rows[0]["leaderboard_valid"] is False
        assert rows[0]["run_date"] == "2026-05-01T00:00:00Z"

    def test_two_rebuilds_are_byte_identical(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        rr.rebuild_index(tmp_path)
        first = (tmp_path / "runs.jsonl").read_bytes()
        rr.rebuild_index(tmp_path)
        assert (tmp_path / "runs.jsonl").read_bytes() == first
        assert first.count(b"\n") == 3

    def test_hand_edits_are_overwritten_from_the_tree(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        (tmp_path / "runs.jsonl").write_text('{"run_id": "hand-edited"}\n')
        rr.rebuild_index(tmp_path)
        assert "hand-edited" not in (tmp_path / "runs.jsonl").read_text()

    def test_in_flight_temp_dirs_and_manifestless_dirs_are_ignored(self, tmp_path: Path) -> None:
        self._populate(tmp_path)
        stray = tmp_path / "results" / "img-a" / ".tmp-run-d-xyz"
        stray.mkdir()
        (stray / "manifest.json").write_text("{}")
        (tmp_path / "results" / "img-a" / "no-manifest-here").mkdir()
        assert [p.name for p in rr.iter_run_dirs(tmp_path)] == ["run-a", "run-c", "run-b"]

    def test_empty_repo_yields_an_empty_index(self, tmp_path: Path) -> None:
        assert rr.rebuild_index(tmp_path) == []
        assert (tmp_path / "runs.jsonl").read_bytes() == b""


# ---------------------------------------------------------------------------
# results-init
# ---------------------------------------------------------------------------


class TestResultsInit:
    def test_cli_lays_out_an_empty_repo(self, tmp_path: Path) -> None:
        target = tmp_path / "results-clone"
        result = CliRunner().invoke(cli_main, ["results-init", str(target)])
        assert result.exit_code == 0, result.output
        assert (target / "AGENTS.md").is_file()
        assert (target / "results" / ".gitkeep").is_file()
        assert (target / "runs.jsonl").read_bytes() == b""
        assert result.output.count("wrote ") == 3

    def test_cli_refuses_a_non_empty_repo(self, tmp_path: Path) -> None:
        rr.init_results_repo(tmp_path)
        result = CliRunner().invoke(cli_main, ["results-init", str(tmp_path)])
        assert result.exit_code != 0
        assert "AGENTS.md exists" in result.output

    def test_agents_md_documents_the_schema(self, tmp_path: Path) -> None:
        rr.init_results_repo(tmp_path)
        text = (tmp_path / "AGENTS.md").read_text()
        for needle in (
            "results/<candidate-hash>/<run-id>/manifest.json",
            "scores.json",
            "Records are immutable",
            "Index is derived",
            "leaderboard_valid",
            "`benchmark`, never `workload`",
            "self-contained",
            "card_correctness",
            "legacy-tree",
            "proposal_status",
        ):
            assert needle in text, needle

    def test_template_is_packaged(self) -> None:
        assert (rr.TEMPLATE_DIR / "AGENTS.md").is_file()
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert "results_repo_templates" in pyproject

    def test_refuses_a_non_empty_target_without_agents_md(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("some other repo")
        with pytest.raises(rr.ResultsRepoError, match="not empty"):
            rr.init_results_repo(tmp_path)
        assert [p.name for p in tmp_path.iterdir()] == ["README.md"]  # nothing written

    def test_never_overwrites_an_existing_index_or_results_tree(self, tmp_path: Path) -> None:
        index_only = tmp_path / "index-only"
        index_only.mkdir()
        (index_only / "runs.jsonl").write_text('{"run_id": "precious"}\n')
        with pytest.raises(rr.ResultsRepoError, match=re.escape("runs.jsonl")):
            rr.init_results_repo(index_only)
        assert (index_only / "runs.jsonl").read_text() == '{"run_id": "precious"}\n'

        results_only = tmp_path / "results-only"
        (results_only / "results" / "img-a").mkdir(parents=True)
        with pytest.raises(rr.ResultsRepoError, match="results"):
            rr.init_results_repo(results_only)
        assert (results_only / "results" / "img-a").is_dir()

    def test_accepts_an_otherwise_empty_git_clone(self, tmp_path: Path) -> None:
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        (clone / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        written = rr.init_results_repo(clone)
        assert len(written) == 3
        assert (clone / "AGENTS.md").is_file()
        assert (clone / ".git" / "HEAD").read_text() == "ref: refs/heads/main\n"

    def test_a_failed_init_rolls_back_and_is_retryable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "brand-new"
        real_write_text = pathlib.Path.write_text

        def flaky(self: Path, *args: Any, **kwargs: Any) -> int:
            if self.name == "runs.jsonl":
                raise OSError("disk full")
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", flaky)
        with pytest.raises(OSError, match="disk full"):
            rr.init_results_repo(target)
        assert not target.exists()  # everything this call created is gone

        monkeypatch.undo()
        rr.init_results_repo(target)
        assert (target / "AGENTS.md").is_file()
        assert (target / "runs.jsonl").read_bytes() == b""

    def test_a_failed_init_leaves_a_preexisting_clone_as_it_was(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        real_write_text = pathlib.Path.write_text

        def flaky(self: Path, *args: Any, **kwargs: Any) -> int:
            if self.name == ".gitkeep":
                raise OSError("disk full")
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", flaky)
        with pytest.raises(OSError, match="disk full"):
            rr.init_results_repo(clone)
        assert sorted(p.name for p in clone.iterdir()) == [".git"]
