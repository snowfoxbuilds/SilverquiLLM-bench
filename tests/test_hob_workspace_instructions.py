"""Platform test: the staged HOB-generation instructions agree with the spec.

`docs/specs/HOB-BENCHMARKS.md` settles the agent envelope for every
HOB-generation benchmark (tests-as-envelope): the workspace engine is freely
modifiable — no additive-only rule, no diff policing — and the three audited
dimensions run against the harvested engine are the entire judgment. The
`AGENTS.md` staged into each HOB-generation workspace (hob-medium today, plus
the smoke benchmark that calibrates the same candidate contract) is what a
candidate actually reads, so it must say the same thing and must not carry the
obsolete SOS-era additive-only prohibition. Verified here, at repository test
time, before any candidate run can consume the docs.

`benchmarks/sos/` is the V1 contract and *keeps* additive-only; it is
deliberately not covered by the envelope assertions below.
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


@pytest.mark.parametrize("benchmark", HOB_GENERATION_WORKSPACES)
class TestStagedInstructionsAgreeWithSpec:
    def test_states_the_spec_envelope(self, benchmark: str) -> None:
        agents = _agents_md(benchmark)
        assert "no additive-only rule and no diff policing" in agents
        for term in ENVELOPE_TERMS:
            assert term.lower() in agents.lower(), (
                f"{benchmark} AGENTS.md lacks the spec's envelope term {term!r}"
            )

    def test_permits_any_engine_modification(self, benchmark: str) -> None:
        """Renames, moves, deletions and refactors are explicitly allowed."""
        agents = _agents_md(benchmark)
        for verb in ("rename", "move", "refactor", "delete"):
            assert re.search(rf"\b{verb}\b", agents), (
                f"{benchmark} AGENTS.md must say engine changes may {verb}"
            )
        assert "the audited tests are the judge" in agents

    def test_names_the_three_audited_dimensions(self, benchmark: str) -> None:
        agents = _agents_md(benchmark).lower()
        assert "target-card correctness" in agents
        assert "fdn card regression" in agents
        assert "engine regression" in agents

    def test_no_obsolete_additive_only_rule(self, benchmark: str) -> None:
        agents = _agents_md(benchmark)
        for pattern in OBSOLETE_PATTERNS:
            assert not re.search(pattern, agents), (
                f"{benchmark} AGENTS.md still carries the obsolete rule {pattern!r}"
            )


class TestSosKeepsItsOwnContract:
    def test_sos_is_not_rewritten_to_the_hob_envelope(self) -> None:
        """The V1 benchmark keeps additive-only; the two contracts stay distinct."""
        sos = _agents_md("sos")
        assert "Additive-only" in sos
        assert "no additive-only rule" not in sos
