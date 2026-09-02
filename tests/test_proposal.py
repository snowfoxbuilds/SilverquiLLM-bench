"""Unit tests for silverquillm.proposal — strict load/validate + commit messages."""

from __future__ import annotations

import json
from pathlib import Path

from silverquillm.proposal import (
    PROPOSAL_INVALID,
    PROPOSAL_MISSING,
    Proposal,
    ProposalError,
    commit_message_with_trailer,
    fallback_commit_message,
    load_proposal,
)


def _job(tmp_path: Path, doc: object | None, *, manifest_version: int | None = 1) -> Path:
    """Build a job dir with an optional proposal doc and manifest schema_version."""
    job = tmp_path / "job"
    (job / "input").mkdir(parents=True)
    (job / "output").mkdir(parents=True)
    if manifest_version is not None:
        (job / "input" / "manifest.json").write_text(
            json.dumps({"schema_version": manifest_version})
        )
    if doc is not None:
        payload = doc if isinstance(doc, str) else json.dumps(doc)
        (job / "output" / "proposal.json").write_text(payload)
    return job


def _valid_doc(**fields: object) -> dict:
    base = {"commit-message": "Do the thing"}
    base.update(fields)
    return {"schema_version": 1, "mode": "run", "fields": base}


class TestValid:
    def test_full_proposal_maps_all_fields(self, tmp_path: Path) -> None:
        doc = _valid_doc(
            **{
                "pr-title": "T",
                "pr-description": "D",
                "decisions": [{"what": "a", "why": "b"}],
                "open-questions": ["q1"],
                "remaining-work": ["r1"],
                "dead-ends": ["d1"],
                "process-issues": [{"friction": "f", "suggested_fix": "s"}],
            }
        )
        p = load_proposal(_job(tmp_path, doc))
        assert isinstance(p, Proposal)
        assert p.commit_message == "Do the thing"
        assert p.pr_title == "T" and p.pr_description == "D"
        assert p.decisions == [{"what": "a", "why": "b"}]
        assert p.open_questions == ["q1"]
        assert p.remaining_work == ["r1"]
        assert p.dead_ends == ["d1"]
        assert p.process_issues == [{"friction": "f", "suggested_fix": "s"}]

    def test_minimal_proposal_defaults_optionals(self, tmp_path: Path) -> None:
        p = load_proposal(_job(tmp_path, _valid_doc()))
        assert isinstance(p, Proposal)
        assert p.decisions == [] and p.open_questions == []
        assert p.pr_title is None and p.pr_description is None


class TestTypedErrors:
    def test_missing_file(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, None))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_MISSING

    def test_invalid_json(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, "{not json"))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_not_an_object(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, [1, 2, 3]))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_unknown_top_level_key(self, tmp_path: Path) -> None:
        doc = _valid_doc()
        doc["extra"] = 1
        err = load_proposal(_job(tmp_path, doc))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_bad_schema_version(self, tmp_path: Path) -> None:
        doc = _valid_doc()
        doc["schema_version"] = 2
        err = load_proposal(_job(tmp_path, doc, manifest_version=None))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_schema_version_mismatch_with_manifest(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, _valid_doc(), manifest_version=2))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_wrong_mode(self, tmp_path: Path) -> None:
        doc = _valid_doc()
        doc["mode"] = "review"
        err = load_proposal(_job(tmp_path, doc))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, _valid_doc(**{"base-branch": "main"})))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_commit_message_required(self, tmp_path: Path) -> None:
        doc = {"schema_version": 1, "mode": "run", "fields": {"pr-title": "x"}}
        err = load_proposal(_job(tmp_path, doc))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_commit_message_empty_rejected(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, _valid_doc(**{"commit-message": "   "})))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_open_questions_must_be_list_of_str(self, tmp_path: Path) -> None:
        err = load_proposal(_job(tmp_path, _valid_doc(**{"open-questions": [1, 2]})))
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_decision_entry_unknown_key_rejected(self, tmp_path: Path) -> None:
        err = load_proposal(
            _job(tmp_path, _valid_doc(decisions=[{"what": "a", "extra": "b"}]))
        )
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID

    def test_process_issue_value_must_be_str(self, tmp_path: Path) -> None:
        err = load_proposal(
            _job(tmp_path, _valid_doc(**{"process-issues": [{"friction": 3}]}))
        )
        assert isinstance(err, ProposalError) and err.status == PROPOSAL_INVALID


class TestCommitMessages:
    def test_trailer_appended(self) -> None:
        msg = commit_message_with_trailer("Body here", "run-9", "smoke", "basic")
        assert msg.startswith("Body here")
        assert "Silverquillm-Run: run-9 / smoke / basic" in msg
        assert msg.endswith("\n")

    def test_fallback_carries_trailer(self) -> None:
        msg = fallback_commit_message("run-9", "smoke", "planned")
        assert "Silverquillm-Run: run-9 / smoke / planned" in msg
        assert "no valid Output Proposal" in msg
