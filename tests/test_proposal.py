"""Unit tests for silverquillm.proposal — validation delegated to production.

The bench does not reimplement the Output Proposal schema; it runs TheOzolith's
``validate_run`` at round one.  These tests pin the bench adapter's status
mapping and prove the validation is the production one (round-one required
fields, unknown-field refusal, wrong-mode refusal) rather than a local copy.
"""

from __future__ import annotations

import json
from pathlib import Path

from theozolith_worker import api

from silverquillm.proposal import (
    PROPOSAL_APPLIED,
    PROPOSAL_INVALID,
    PROPOSAL_MISSING,
    fallback_commit_message,
    load_proposal,
)


def _job(tmp_path: Path, doc: object | None) -> Path:
    job = tmp_path / "job"
    (job / "output").mkdir(parents=True)
    if doc is not None:
        payload = doc if isinstance(doc, str) else json.dumps(doc)
        (job / "output" / "proposal.json").write_text(payload)
    return job


def _valid_doc(**fields: object) -> dict:
    base = {"pr-title": "T", "pr-description": "D", "commit-message": "Do the thing"}
    base.update(fields)
    return {"schema_version": 1, "mode": "run", "fields": base}


class TestApplied:
    def test_full_proposal_validates_via_production(self, tmp_path: Path) -> None:
        doc = _valid_doc(
            decisions=[{"what": "a", "why": "b"}],
            **{"open-questions": ["q1"], "dead-ends": ["d1"]},
        )
        result = load_proposal(_job(tmp_path, doc))
        assert result.status == PROPOSAL_APPLIED
        assert isinstance(result.proposal, api.RunProposal)
        assert result.proposal.commit_message == "Do the thing"
        assert result.proposal.pr_title == "T" and result.proposal.pr_description == "D"
        assert result.proposal.section.decisions[0].what == "a"
        assert result.proposal.section.open_questions == ["q1"]


class TestStatuses:
    def test_missing_file(self, tmp_path: Path) -> None:
        result = load_proposal(_job(tmp_path, None))
        assert result.status == PROPOSAL_MISSING and result.proposal is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        assert load_proposal(_job(tmp_path, "{not json")).status == PROPOSAL_INVALID

    def test_not_an_object(self, tmp_path: Path) -> None:
        assert load_proposal(_job(tmp_path, [1, 2, 3])).status == PROPOSAL_INVALID

    def test_round_one_requires_pr_fields(self, tmp_path: Path) -> None:
        """Delegation is real: a proposal the bench's old lenient copy accepted
        (commit-message only) is rejected — production requires pr-title and
        pr-description on the round that creates the PR (round one)."""
        doc = {"schema_version": 1, "mode": "run", "fields": {"commit-message": "m"}}
        result = load_proposal(_job(tmp_path, doc))
        assert result.status == PROPOSAL_INVALID
        assert any("pr-title" in e for e in result.errors)

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        result = load_proposal(_job(tmp_path, _valid_doc(**{"base-branch": "main"})))
        assert result.status == PROPOSAL_INVALID

    def test_wrong_mode(self, tmp_path: Path) -> None:
        doc = _valid_doc()
        doc["mode"] = "review"
        assert load_proposal(_job(tmp_path, doc)).status == PROPOSAL_INVALID

    def test_open_questions_must_be_list_of_str(self, tmp_path: Path) -> None:
        result = load_proposal(_job(tmp_path, _valid_doc(**{"open-questions": [1, 2]})))
        assert result.status == PROPOSAL_INVALID

    def test_decision_entry_unknown_key_rejected(self, tmp_path: Path) -> None:
        result = load_proposal(
            _job(tmp_path, _valid_doc(decisions=[{"what": "a", "extra": "b"}]))
        )
        assert result.status == PROPOSAL_INVALID


class TestFallbackCommitMessage:
    def test_carries_the_production_trailer(self) -> None:
        msg = fallback_commit_message("run-9")
        assert "Ozolith-Run: run-9" in msg
        assert "no valid Output Proposal" in msg.lower() or "no valid output proposal" in msg.lower()
        assert msg.rstrip().endswith("Ozolith-Round: 1")
