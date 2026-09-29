"""Platform test: the staged HOB-generation instructions agree with the spec.

`docs/specs/HOB-BENCHMARKS.md` settles the agent envelope for every
HOB-generation benchmark: the workspace engine is freely modifiable — no
additive-only rule, no diff policing. The `AGENTS.md` staged into each
HOB-generation workspace (hob-medium today, plus the smoke benchmark that
calibrates the same candidate contract) is what a candidate actually reads, so
it must grant that freedom, say that the engine may be deficient, and never
describe how the run is evaluated. Verified here, at repository test time,
before any candidate run can consume the docs.

`benchmarks/sos/` is the V1 contract and *keeps* additive-only; it is
deliberately not covered by the assertions below.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "docs" / "specs" / "HOB-BENCHMARKS.md"
HOB_GENERATION_WORKSPACES = ["hob-medium", "smoke"]

# Vocabulary the spec's envelope ruling and the staged instructions must share.
ENVELOPE_TERMS = [
    "additive-only",
    "diff policing",
    "harvested engine",
    "FDN card regression",
    "engine regression",
]

# The SOS-era prohibition, in every form it appeared in the staged docs.
OBSOLETE_PATTERNS = [
    r"Additive-only",
    r"MUST NOT rename",
    r"Must NOT\*\*: Rename",
    r"no renaming, no refactoring",
    r"break the grader's imports",
    r"zero your score",
    r"import stability",
]


def _agents_md(benchmark: str) -> str:
    """AGENTS.md with line wrapping collapsed, so phrase checks survive reflow."""
    text = (REPO_ROOT / "benchmarks" / benchmark / "workspace" / "AGENTS.md").read_text()
    return re.sub(r"\s+", " ", text)


def _spec_envelope() -> str:
    """The spec's `Agent envelope` bullet under `## Engine rules`."""
    text = SPEC.read_text()
    m = re.search(r"^- \*\*Agent envelope\*\*:(.+?)(?=^- |\n## )", text, re.MULTILINE | re.DOTALL)
    assert m, "HOB-BENCHMARKS.md must carry the `Agent envelope` engine rule"
    return m.group(1)


class TestSpecEnvelope:
    def test_spec_states_tests_as_envelope(self) -> None:
        envelope = _spec_envelope()
        assert "no additive-only rule, no diff policing" in envelope
        for term in ENVELOPE_TERMS:
            assert term.lower() in envelope.lower(), f"spec envelope lacks {term!r}"


# Evaluation vocabulary no agent-visible document may use: the workspace
# describes the task, never how it is judged (HOB-BENCHMARKS.md, Instruction
# documents).
EVALUATION_PATTERNS = [
    r"\baudited\b",
    r"hidden tests?",
    r"\bgrad(?:er|ing|ed)\b",
    r"\boracle\b",
    r"\bscor(?:e|es|ed|ing)\b",
    r"authoritative (?:tests?|suites?)",
    r"\bjudge",
    r"benchmark's",
    r"harness",
    r"host-side",
]

DEFICIENCIES_LINE = (
    "The engine may have deficiencies and bugs. It's your job to make sure your "
    "implementations behave correctly according to the rules in `RULEBOOK.txt`, and "
    "that your changes don't break existing cards."
)


def _workspace_documents(benchmark: str) -> list[Path]:
    workspace = REPO_ROOT / "benchmarks" / benchmark / "workspace"
    return [path for path in sorted(workspace.rglob("*.md")) if "__pycache__" not in path.parts]


@pytest.mark.parametrize("benchmark", HOB_GENERATION_WORKSPACES)
class TestStagedInstructions:
    def test_permits_any_engine_modification(self, benchmark: str) -> None:
        """Renames, moves, deletions and refactors are explicitly allowed."""
        agents = _agents_md(benchmark)
        assert "The engine is yours to change" in agents
        for verb in ("rename", "move", "refactor", "delete"):
            assert re.search(rf"\b{verb}\b", agents), (
                f"{benchmark} AGENTS.md must say engine changes may {verb}"
            )

    def test_states_that_the_engine_may_be_deficient(self, benchmark: str) -> None:
        assert DEFICIENCIES_LINE in _agents_md(benchmark)

    def test_no_obsolete_additive_only_rule(self, benchmark: str) -> None:
        agents = _agents_md(benchmark)
        for pattern in OBSOLETE_PATTERNS:
            assert not re.search(pattern, agents), (
                f"{benchmark} AGENTS.md still carries the obsolete rule {pattern!r}"
            )

    def test_documents_never_describe_evaluation(self, benchmark: str) -> None:
        documents = _workspace_documents(benchmark)
        assert documents
        for path in documents:
            text = re.sub(r"\s+", " ", path.read_text())
            for pattern in EVALUATION_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                assert not match, f"{path} mentions {match.group(0)!r}"

    def test_engine_development_records_are_not_staged(self, benchmark: str) -> None:
        workspace = REPO_ROOT / "benchmarks" / benchmark / "workspace"
        for name in ("KEY_DECISIONS.md", "DROPPED_COVERAGE.md"):
            assert not (workspace / name).exists()


class TestSosKeepsItsOwnContract:
    def test_sos_is_not_rewritten_to_the_hob_envelope(self) -> None:
        """The V1 benchmark keeps additive-only; the two contracts stay distinct."""
        sos = _agents_md("sos")
        assert "Additive-only" in sos
        assert "no additive-only rule" not in sos
