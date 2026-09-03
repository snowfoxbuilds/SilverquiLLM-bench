"""Structural tests for TODO item 7: .claude/skills/test-investigation/SKILL.md

Verify the SKILL.md file has valid frontmatter with required keys, documents
both Investigation and Discovery modes, states the Released-tier refusal rule,
references the correct dataset paths, and declares outputs as human-reviewable
reports only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Try PyYAML first; fall back to a minimal manual parser.
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "test-investigation" / "SKILL.md"


# ---------------------------------------------------------------------------
# Helper: parse YAML frontmatter
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Extract and parse YAML frontmatter between the first two '---' lines."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("File does not start with '---' frontmatter delimiter")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("No closing '---' frontmatter delimiter found")
    fm_block = "\n".join(lines[1:end_idx])
    if _HAS_YAML:
        return yaml.safe_load(fm_block)
    # Minimal manual parser: handles key: value and key:\n  - item lists
    result: dict = {}
    current_key: str | None = None
    for line in fm_block.split("\n"):
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and current_key is not None:
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(list_match.group(1).strip())
            continue
        kv_match = re.match(r"^(\S[^:]*?):\s*(.*)$", line)
        if kv_match:
            key = kv_match.group(1).strip()
            val = kv_match.group(2).strip()
            current_key = key
            if val and val != ">":
                result[key] = val
            elif val == ">":
                # YAML folded scalar — collect continuation lines
                result[key] = ""
            else:
                result[key] = None
            continue
        # Continuation of folded scalar
        if current_key is not None and isinstance(result.get(current_key), str) and line.strip():
            if result[current_key]:
                result[current_key] += " " + line.strip()
            else:
                result[current_key] = line.strip()
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_text() -> str:
    """Read the SKILL.md file content once."""
    assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict:
    """Parse and return the YAML frontmatter as a dict."""
    return _parse_frontmatter(skill_text)


@pytest.fixture(scope="module")
def body(skill_text: str) -> str:
    """Return the body (everything after the closing frontmatter '---')."""
    lines = skill_text.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    assert end_idx is not None, "Missing closing frontmatter delimiter"
    return "\n".join(lines[end_idx + 1:])


# ---------------------------------------------------------------------------
# Test 1: File existence
# ---------------------------------------------------------------------------

class TestSkillFileExists:
    """The SKILL.md file must exist at the expected path."""

    def test_file_exists(self) -> None:
        assert SKILL_PATH.exists(), (
            f"Expected SKILL.md at {SKILL_PATH.relative_to(REPO_ROOT)}"
        )


# ---------------------------------------------------------------------------
# Test 2: Valid YAML frontmatter block
# ---------------------------------------------------------------------------

class TestFrontmatterValid:
    """The file must start with valid YAML frontmatter between --- delimiters."""

    def test_starts_with_frontmatter_delimiter(self, skill_text: str) -> None:
        assert skill_text.startswith("---"), "SKILL.md must start with '---'"

    def test_frontmatter_parses(self, frontmatter: dict) -> None:
        assert isinstance(frontmatter, dict), "Frontmatter must parse as a dict"


# ---------------------------------------------------------------------------
# Test 3: name == 'test-investigation'
# ---------------------------------------------------------------------------

class TestFrontmatterName:
    def test_name_equals_test_investigation(self, frontmatter: dict) -> None:
        assert frontmatter.get("name") == "test-investigation", (
            f"Expected name 'test-investigation', got {frontmatter.get('name')!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: description is non-empty and conveys invocation context
# ---------------------------------------------------------------------------

class TestFrontmatterDescription:
    def test_description_is_nonempty_string(self, frontmatter: dict) -> None:
        desc = frontmatter.get("description")
        assert isinstance(desc, str) and len(desc.strip()) > 0, (
            "Frontmatter 'description' must be a non-empty string"
        )

    def test_description_conveys_when_to_invoke(self, frontmatter: dict) -> None:
        """Description should mention triage/failing tests or discovery context."""
        desc = frontmatter["description"].lower()
        assert any(word in desc for word in ("triage", "failing", "investigation", "discover")), (
            "Description should convey when to invoke the skill"
        )


# ---------------------------------------------------------------------------
# Test 5: allowed-tools declared and non-empty
# ---------------------------------------------------------------------------

class TestFrontmatterAllowedTools:
    def test_allowed_tools_key_exists(self, frontmatter: dict) -> None:
        assert "allowed-tools" in frontmatter, (
            "Frontmatter must have an 'allowed-tools' key"
        )

    def test_allowed_tools_is_nonempty_list(self, frontmatter: dict) -> None:
        tools = frontmatter["allowed-tools"]
        assert isinstance(tools, list) and len(tools) > 0, (
            "'allowed-tools' must be a non-empty list"
        )


# ---------------------------------------------------------------------------
# Test 6: Body references the dataset path
# ---------------------------------------------------------------------------

class TestDatasetPath:
    def test_harvested_results_jsonl_path(self, body: str) -> None:
        """Body should reference the harvested_results.jsonl path template or concrete SOS path."""
        # The template form uses <bench> placeholder
        assert "harvested_results.jsonl" in body, (
            "Body must reference harvested_results.jsonl dataset"
        )
        # Check the template path pattern
        assert "benchmarks/" in body and "analysis/harvested_results.jsonl" in body, (
            "Body must reference benchmarks/<bench>/analysis/harvested_results.jsonl"
        )


# ---------------------------------------------------------------------------
# Test 7: Released-tier refusal rule and permitted tiers
# ---------------------------------------------------------------------------

class TestBenchmarkTierRules:
    def test_config_json_tier_reference(self, body: str) -> None:
        """Body must state that tier is read from config.json."""
        assert "config.json" in body, "Body must reference config.json for tier"
        assert "tier" in body.lower(), "Body must mention the 'tier' field"

    def test_released_tier_refusal(self, body: str) -> None:
        """Body must state refusal when tier is Released."""
        # Look for 'Released' in a refusal context
        assert "Released" in body, "Body must mention 'Released' tier"
        body_lower = body.lower()
        assert "refuse" in body_lower, (
            "Body must state a refusal rule for Released tier"
        )

    def test_beta_tier_mentioned(self, body: str) -> None:
        assert "Beta" in body, "Body must mention 'Beta' as a permitted tier"

    def test_benchmarking_tier_mentioned(self, body: str) -> None:
        assert "Benchmarking" in body, "Body must mention 'Benchmarking' as a permitted tier"


# ---------------------------------------------------------------------------
# Test 8: Both modes documented
# ---------------------------------------------------------------------------

class TestBothModes:
    def test_investigation_mode_documented(self, body: str) -> None:
        """Body must document Investigation mode."""
        assert "Investigation" in body, "Body must document Investigation mode"

    def test_discovery_mode_documented(self, body: str) -> None:
        """Body must document Discovery mode."""
        assert "Discovery" in body, "Body must document Discovery mode"

    def test_both_modes_have_headings(self, body: str) -> None:
        """Both modes should appear as section headings (## or ###)."""
        assert re.search(r"^#+\s+.*Investigation", body, re.MULTILINE), (
            "Investigation mode should have a heading"
        )
        assert re.search(r"^#+\s+.*Discovery", body, re.MULTILINE), (
            "Discovery mode should have a heading"
        )


# ---------------------------------------------------------------------------
# Test 9: Outputs are human-reviewable only / no auto-editing
# ---------------------------------------------------------------------------

class TestOutputsHumanReviewable:
    def test_human_reviewable_report(self, body: str) -> None:
        """Body must state outputs are human-reviewable reports."""
        assert "human-reviewable report" in body.lower() or "human-reviewable report" in body, (
            "Body must state outputs are a human-reviewable report"
        )

    def test_no_committed_test_edits(self, body: str) -> None:
        """Body must state no committed test edits."""
        body_lower = body.lower()
        assert "no committed test edits" in body_lower, (
            "Body must state 'no committed test edits'"
        )

    def test_human_decides(self, body: str) -> None:
        """Body must indicate the human makes the final call."""
        assert "human" in body.lower() and "decides" in body.lower(), (
            "Body must state that the human decides / makes the final call"
        )


# ---------------------------------------------------------------------------
# Test 10: References audited tests path and the canonical AUDITED-TEST-SUITE.md
# ---------------------------------------------------------------------------

# Matches a Markdown inline link and captures its target: [text](target)
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class TestAuditedTestsReference:
    def test_audited_path_referenced(self, body: str) -> None:
        """Body must reference the canonical audited tests path."""
        assert "benchmarks/sos/data/tests/audited/" in body, (
            "Body must reference benchmarks/sos/data/tests/audited/ path"
        )

    def test_audited_test_suite_md_link_resolves(self, body: str) -> None:
        """Body must link to the canonical AUDITED-TEST-SUITE.md spec, and that
        link target must resolve to a file that exists on disk.

        Exact-target assertion (not a substring check): it fails if the link is
        missing, or malformed / pointing at a nonexistent file.
        """
        targets = [t.strip() for t in _MD_LINK_RE.findall(body)]
        suite_links = [
            t for t in targets
            if Path(t.split("#", 1)[0]).name == "AUDITED-TEST-SUITE.md"
        ]
        assert suite_links, (
            "Body must contain a Markdown link to AUDITED-TEST-SUITE.md "
            "(the canonical audited-test spec)"
        )
        for target in suite_links:
            rel = target.split("#", 1)[0]
            resolved = (SKILL_PATH.parent / rel).resolve()
            assert resolved.is_file(), (
                f"AUDITED-TEST-SUITE.md link target {target!r} does not resolve "
                f"to an existing file (resolved to {resolved})"
            )
