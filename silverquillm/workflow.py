"""Benchmark-owned intake and proposal composition, independent of any runtime package."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from silverquillm import decisions
from silverquillm.gate import Finding, GateResult, run_gate
from silverquillm.proposal_schema import (
    PROPOSAL_FILE,
    SCHEMA_VERSION,
    validate_run,
)
from silverquillm.safe_files import atomic_write

__all__ = ["PROPOSAL_FILE", "Finding", "GateResult", "run_gate", "validate_run"]

PROMPT_FILE = "input/prompt.md"
STATUS_FILE = "output/status.json"
TRANSCRIPT_FILE = "output/transcript.txt"
CONTAINER_JOB_PATH = "/job"
MODE_RUN = "run"


@dataclass
class Issue:
    number: int
    title: str
    body: str
    labels: set = field(default_factory=set)
    assignees: list = field(default_factory=list)
    is_pr: bool = False


@dataclass
class ContextSnapshot:
    issue: Issue
    issue_comments: list = field(default_factory=list)
    timeline: list = field(default_factory=list)


@dataclass
class Manifest:
    run_id: str
    mode: str = "run"
    adapter: str = "configured"
    agent_timeout_seconds: float = 3600
    round: int = 1
    round_budget: int = 0
    schema_version: int = SCHEMA_VERSION
    workdir: str = "checkout"


def write_manifest(root, manifest):
    from dataclasses import asdict

    atomic_write(Path(root) / "input/benchmark.json", json.dumps(asdict(manifest), sort_keys=True))


def render_run_prompt(
    issue,
    round_number=1,
    revised_plan=None,
    *,
    input_path="/input",
    proposal_path="/output/proposal.json",
):
    if round_number != 1 or revised_plan is not None:
        raise ValueError("benchmark modes use a fresh first-round task")
    template = Path(__file__).with_name("prompt_template.txt").read_text()
    text = template.format(
        number=issue.number,
        title=issue.title,
        body=issue.body or "(no body)",
        round_context="",
        job="/job",
        deps_bullet="",
    )
    text = text.replace("/job/input", input_path)
    return text + (
        "\n## Standalone benchmark file interface\n\n"
        "This is a local benchmark with no GitHub publication authority or upstream context. "
        "The benchmark will evaluate the checkout after the configured container exits. "
        "The Output Proposal fields and Decisions Section above remain required. "
        "Write the equivalent JSON document directly to `" + proposal_path + "`: "
        '`{"schema_version":1,"mode":"run","fields":{"pr-title":"...","pr-description":"...","commit-message":"...","decisions":[{"what":"...","why":"..."}]}}`. '
        "Include the other described fields when applicable. An unchanged checkout still needs no-change reasoning.\n"
    )


def write_tree(root, snapshot):
    root = Path(root) / "issue"
    (root / "comments").mkdir(parents=True, exist_ok=True)
    atomic_write(root / "comments/INDEX.md", "No external comments supplied.\n")
    atomic_write(root / "timeline.md", "Synthetic benchmark issue; no external timeline.\n")
    atomic_write(root / "body.md", snapshot.issue.body)


def commit_message_with_trailer(proposed: str, run_id: str, issue_number: int, round_n: int) -> str:
    """The proposed commit message plus the provenance trailer (ADR-0046).
    The previously generated ``Run <id> for #<N> (round <r>)`` subject is
    demoted to these trailer facts; the agent-authored message is the
    archival copy of the round's context — no fallback ever ships."""
    return (
        f"{proposed.rstrip()}\n"
        "\n"
        f"Ozolith-Run: {run_id}\n"
        f"Ozolith-Issue: #{issue_number}\n"
        f"Ozolith-Round: {round_n}\n"
    )


def compose_pr_body(
    issue_number: int,
    narrative: str,
    section: decisions.DecisionsSection,
    *,
    no_change_intro: str = "",
) -> str:
    """Zone composition (ADR-0046): Closes line + narrative + Decisions
    Section. The driver owns the frame; the proposal supplies the content."""
    zones = [f"Closes #{issue_number}."]
    if no_change_intro:
        zones.append(no_change_intro)
    if narrative.strip():
        zones.append(narrative.strip())
    return decisions.upsert("\n\n".join(zones), section)
