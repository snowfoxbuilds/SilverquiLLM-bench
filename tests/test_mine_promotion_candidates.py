"""Tests for scripts/mine_promotion_candidates.py — discovery-candidate miner.

Validates that the miner surfaces agent-written test behaviors NOT represented
in the canonical audited suite, and that covered behaviors (by name match or
API-overlap + docstring keyword overlap) are correctly suppressed.

Fixture layout under tmp_path::

    docker/<image>/validated_results/<run>/cards/<card>/tests.py  (agent tests)
    benchmarks/sos/data/tests/audited/sos/<card>/tests.py        (audited tests)
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import the script module via importlib (scripts/ is not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "mine_promotion_candidates.py"

_spec = importlib.util.spec_from_file_location(
    "mine_promotion_candidates", _SCRIPT_PATH
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["mine_promotion_candidates"] = _mod
_spec.loader.exec_module(_mod)

mine_candidates = _mod.mine_candidates
Candidate = _mod.Candidate
extract_test_behaviors = _mod.extract_test_behaviors
is_behavior_covered = _mod.is_behavior_covered
main = _mod.main
format_candidates_text = _mod.format_candidates_text
format_candidates_json = _mod.format_candidates_json
_normalize_test_name = _mod._normalize_test_name


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_agent_tests(
    root: Path,
    image: str,
    run: str,
    card: str,
    source: str,
) -> Path:
    """Write an agent tests.py into the validated results tree."""
    d = root / "docker" / image / "validated_results" / run / "cards" / card
    d.mkdir(parents=True, exist_ok=True)
    f = d / "tests.py"
    f.write_text(textwrap.dedent(source))
    return f


def _write_audited_tests(
    root: Path,
    card: str,
    source: str,
    bench: str = "sos",
) -> Path:
    """Write an audited tests.py into the audited suite tree."""
    d = root / "benchmarks" / bench / "data" / "tests" / "audited" / bench / card
    d.mkdir(parents=True, exist_ok=True)
    f = d / "tests.py"
    f.write_text(textwrap.dedent(source))
    return f


# ---------------------------------------------------------------------------
# 1. SPEC: Novel behavior IS surfaced as a Candidate
# ---------------------------------------------------------------------------


class TestNovelBehaviorSurfaced:
    """An agent test exercising a behavior absent from the audited file is surfaced."""

    def test_novel_behavior_is_candidate(self, tmp_path: Path) -> None:
        _write_audited_tests(tmp_path, "sos_100", """\
            def test_basic_attack(engine):
                \"\"\"Check basic attack value.\"\"\"
                card = engine.create_card("test")
                assert card.power == 2
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_100", """\
            def test_flying_ability(engine):
                \"\"\"Verify the card has flying.\"\"\"
                card = engine.create_card("test")
                assert card.has_ability("flying")
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.card == "sos_100"
        assert c.image == "imgA"
        assert c.run == "run1"
        assert c.test_name == "test_flying_ability"
        assert c.source_snippet  # non-empty

    def test_candidate_normalized_name_present(self, tmp_path: Path) -> None:
        _write_audited_tests(tmp_path, "sos_100", """\
            def test_basic(engine):
                pass
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_100", """\
            def test_novel_behavior(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].normalized_name == "novel_behavior"


# ---------------------------------------------------------------------------
# 2. SPEC: Name-matched behavior NOT surfaced (Rule 1)
# ---------------------------------------------------------------------------


class TestNameMatchSuppressed:
    """An agent test whose normalized name matches an audited test is NOT surfaced."""

    def test_same_normalized_name_not_surfaced(self, tmp_path: Path) -> None:
        _write_audited_tests(tmp_path, "sos_200", """\
            def test_creature_power(engine):
                \"\"\"Check creature power.\"\"\"
                assert engine.get_card().power == 3
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_200", """\
            def test_creature_power(engine):
                \"\"\"Creature power check from agent.\"\"\"
                assert engine.get_card().power == 3
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 0

    def test_name_match_ignores_test_prefix_and_case_suffix(self, tmp_path: Path) -> None:
        """test_foo_case and test_foo should normalize to the same thing (foo)."""
        _write_audited_tests(tmp_path, "sos_201", """\
            def test_foo(engine):
                pass
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_201", """\
            def test_foo_case(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 0


# ---------------------------------------------------------------------------
# 3. API-overlap rule (Rule 2): Jaccard >= 0.8 AND shared docstring keyword
# ---------------------------------------------------------------------------


class TestApiOverlapRule:
    """API-overlap matching with docstring keyword overlap."""

    def test_high_api_overlap_and_shared_keyword_not_surfaced(self, tmp_path: Path) -> None:
        """Jaccard >= 0.8 AND shared docstring keyword -> NOT surfaced."""
        # Audited: uses engine.create_card, card.power, assertEqual
        _write_audited_tests(tmp_path, "sos_300", """\
            def test_audited_check(engine):
                \"\"\"Verify creature power value.\"\"\"
                card = engine.create_card("X")
                result = card.power
                assert result == 3
        """)
        # Agent: different name, same APIs, shares docstring keyword "creature"
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_300", """\
            def test_different_name(engine):
                \"\"\"Check creature strength.\"\"\"
                card = engine.create_card("X")
                result = card.power
                assert result == 3
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 0

    def test_high_api_overlap_but_no_shared_keyword_surfaced(self, tmp_path: Path) -> None:
        """Jaccard >= 0.8 but NO shared docstring keyword -> IS surfaced (Rule 2 requires both)."""
        _write_audited_tests(tmp_path, "sos_301", """\
            def test_audited_check(engine):
                \"\"\"Verify creature power value.\"\"\"
                card = engine.create_card("X")
                result = card.power
                assert result == 3
        """)
        # Agent: same APIs, but docstring has no meaningful keyword overlap (all words <= 3 chars or different)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_301", """\
            def test_agent_different(engine):
                \"\"\"Validate toughness rating.\"\"\"
                card = engine.create_card("X")
                result = card.power
                assert result == 3
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].test_name == "test_agent_different"

    def test_low_api_overlap_with_shared_keyword_still_surfaced(self, tmp_path: Path) -> None:
        """Low API Jaccard (< 0.8) even with shared keyword -> IS surfaced."""
        _write_audited_tests(tmp_path, "sos_302", """\
            def test_audited(engine):
                \"\"\"Check creature stats.\"\"\"
                card = engine.create_card("X")
                assert card.power == 3
        """)
        # Agent: very different API set, but shares keyword "creature"
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_302", """\
            def test_agent_unique(engine):
                \"\"\"Check creature abilities.\"\"\"
                result = engine.get_abilities("Y")
                assert "flying" in result
                engine.activate_ability("flying")
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].test_name == "test_agent_unique"


# ---------------------------------------------------------------------------
# 4. Missing audited file -> all behaviors surfaced with note
# ---------------------------------------------------------------------------


class TestMissingAuditedFile:
    """When no audited tests.py exists, all agent behaviors are candidates."""

    def test_all_surfaced_with_no_audited_baseline_note(self, tmp_path: Path) -> None:
        # No audited file for sos_400
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_400", """\
            def test_alpha(engine):
                pass

            def test_beta(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 2
        for c in candidates:
            assert c.note == "no audited baseline"
            assert c.card == "sos_400"

    def test_missing_audited_candidate_names(self, tmp_path: Path) -> None:
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_401", """\
            def test_gamma(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].test_name == "test_gamma"
        assert candidates[0].note == "no audited baseline"


# ---------------------------------------------------------------------------
# 5. --card filter narrows mining
# ---------------------------------------------------------------------------


class TestCardFilter:
    """card= argument restricts mining to that card only."""

    def test_card_filter_narrows_to_single_card(self, tmp_path: Path) -> None:
        # Two cards in same run, no audited files -> both would be surfaced
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_500", """\
            def test_one(engine):
                pass
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_501", """\
            def test_two(engine):
                pass
        """)

        all_candidates = mine_candidates(tmp_path)
        assert len(all_candidates) == 2

        filtered = mine_candidates(tmp_path, card="sos_500")
        assert len(filtered) == 1
        assert filtered[0].card == "sos_500"

    def test_card_filter_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_500", """\
            def test_one(engine):
                pass
        """)

        filtered = mine_candidates(tmp_path, card="sos_999")
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# 6. SyntaxError robustness: bad file is skipped, others still mine
# ---------------------------------------------------------------------------


class TestSyntaxErrorRobustness:
    """A SyntaxError in an agent tests.py does not crash; other cards still mine."""

    def test_syntax_error_skipped_other_cards_still_mine(self, tmp_path: Path) -> None:
        # Bad syntax
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_600", """\
            def test_broken(engine)
                pass  # missing colon -> SyntaxError
        """)
        # Valid card
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_601", """\
            def test_valid(engine):
                pass
        """)

        # Should not raise
        candidates = mine_candidates(tmp_path)
        # Only the valid card's test should appear
        assert len(candidates) == 1
        assert candidates[0].card == "sos_601"
        assert candidates[0].test_name == "test_valid"

    def test_syntax_error_in_audited_file_treated_as_missing(self, tmp_path: Path) -> None:
        """If audited tests.py has a SyntaxError, treat as missing (all agent behaviors surfaced)."""
        _write_audited_tests(tmp_path, "sos_602", """\
            def test_broken(engine)
                pass  # SyntaxError
        """)
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_602", """\
            def test_agent_fn(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        # When audited is unparseable, note should indicate no audited baseline
        assert candidates[0].note == "no audited baseline"


# ---------------------------------------------------------------------------
# 7. Provenance: correct (image, run) per candidate
# ---------------------------------------------------------------------------


class TestProvenance:
    """Candidates carry the correct (image, run) of the source agent run."""

    def test_two_runs_trace_to_correct_provenance(self, tmp_path: Path) -> None:
        # Two different runs produce candidates for the same card
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_700", """\
            def test_from_run1(engine):
                pass
        """)
        _write_agent_tests(tmp_path, "imgB", "run2", "sos_700", """\
            def test_from_run2(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        by_test = {c.test_name: c for c in candidates}

        assert "test_from_run1" in by_test
        assert by_test["test_from_run1"].image == "imgA"
        assert by_test["test_from_run1"].run == "run1"

        assert "test_from_run2" in by_test
        assert by_test["test_from_run2"].image == "imgB"
        assert by_test["test_from_run2"].run == "run2"

    def test_same_image_different_runs(self, tmp_path: Path) -> None:
        """Two runs under the same image produce separate candidates."""
        _write_agent_tests(tmp_path, "imgA", "runX", "sos_701", """\
            def test_alpha(engine):
                pass
        """)
        _write_agent_tests(tmp_path, "imgA", "runY", "sos_701", """\
            def test_beta(engine):
                pass
        """)

        candidates = mine_candidates(tmp_path)
        runs = {(c.image, c.run) for c in candidates}
        assert ("imgA", "runX") in runs
        assert ("imgA", "runY") in runs


# ---------------------------------------------------------------------------
# 8. CLI / main(): outputs candidates, never promotes
# ---------------------------------------------------------------------------


class TestCLI:
    """CLI entry point outputs candidates and never modifies the audited tree."""

    def test_main_text_output_contains_candidate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_800", """\
            def test_novel(engine):
                \"\"\"A novel test.\"\"\"
                pass
        """)

        with mock.patch("sys.argv", ["mine_promotion_candidates.py", "--format", "text"]):
            main(repo_root=tmp_path)

        captured = capsys.readouterr()
        assert "sos_800" in captured.out
        assert "test_novel" in captured.out

    def test_main_json_output_parseable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_801", """\
            def test_json_out(engine):
                pass
        """)

        with mock.patch("sys.argv", ["mine_promotion_candidates.py", "--format", "json"]):
            main(repo_root=tmp_path)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["card"] == "sos_801"
        assert data[0]["test_name"] == "test_json_out"

    def test_main_never_writes_to_audited_tree(self, tmp_path: Path) -> None:
        """CLI must never promote (write) to the audited tree."""
        audited_path = _write_audited_tests(tmp_path, "sos_802", """\
            def test_existing(engine):
                pass
        """)
        audited_content_before = audited_path.read_text()
        audited_mtime_before = audited_path.stat().st_mtime

        _write_agent_tests(tmp_path, "imgA", "run1", "sos_802", """\
            def test_novel_agent(engine):
                pass
        """)

        with mock.patch("sys.argv", ["mine_promotion_candidates.py"]):
            main(repo_root=tmp_path)

        # Audited file must be unchanged
        assert audited_path.read_text() == audited_content_before
        assert audited_path.stat().st_mtime == audited_mtime_before

        # No new files in the audited card directory
        audited_dir = audited_path.parent
        assert sorted(f.name for f in audited_dir.iterdir()) == ["tests.py"]

    def test_main_no_candidates_text(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When there are no candidates, text output says so."""
        # No agent tests -> no candidates
        with mock.patch("sys.argv", ["mine_promotion_candidates.py"]):
            main(repo_root=tmp_path)

        captured = capsys.readouterr()
        assert "No promotion candidates" in captured.out


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """_normalize_test_name strips prefix and suffixes correctly."""

    def test_strip_test_prefix(self) -> None:
        assert _normalize_test_name("test_foo") == "foo"

    def test_strip_test_suffix(self) -> None:
        assert _normalize_test_name("test_bar_test") == "bar"

    def test_strip_case_suffix(self) -> None:
        assert _normalize_test_name("test_baz_case") == "baz"

    def test_lowercase(self) -> None:
        assert _normalize_test_name("Test_Foo_Bar") == "foo_bar"


class TestExtractBehaviors:
    """extract_test_behaviors extracts all test functions with correct metadata."""

    def test_extracts_async_test_functions(self) -> None:
        source = textwrap.dedent("""\
            async def test_async_fn(engine):
                \"\"\"Async test docstring.\"\"\"
                await engine.run()
        """)
        behaviors = extract_test_behaviors(source)
        assert len(behaviors) == 1
        assert behaviors[0].name == "test_async_fn"
        assert "Async test docstring" in behaviors[0].docstring

    def test_extracts_test_in_class(self) -> None:
        source = textwrap.dedent("""\
            class TestSuite:
                def test_method(self):
                    pass
        """)
        behaviors = extract_test_behaviors(source)
        assert len(behaviors) == 1
        assert behaviors[0].name == "test_method"

    def test_non_test_functions_ignored(self) -> None:
        source = textwrap.dedent("""\
            def helper_function():
                pass

            def test_real():
                pass
        """)
        behaviors = extract_test_behaviors(source)
        assert len(behaviors) == 1
        assert behaviors[0].name == "test_real"

    def test_engine_apis_extracted(self) -> None:
        source = textwrap.dedent("""\
            def test_apis(engine):
                card = engine.create_card("X")
                result = card.power
                assert result == 3
        """)
        behaviors = extract_test_behaviors(source)
        apis = behaviors[0].engine_apis
        assert "create_card" in apis
        assert "power" in apis


class TestIsBehaviorCovered:
    """is_behavior_covered applies the two matching rules correctly."""

    def test_name_match_returns_covered(self) -> None:
        source_agent = "def test_foo(e):\n    pass\n"
        source_audited = "def test_foo(e):\n    pass\n"
        agent = extract_test_behaviors(source_agent)[0]
        audited = extract_test_behaviors(source_audited)
        assert is_behavior_covered(agent, audited) is True

    def test_no_match_returns_not_covered(self) -> None:
        source_agent = "def test_unique(e):\n    e.fly()\n"
        source_audited = "def test_other(e):\n    e.swim()\n"
        agent = extract_test_behaviors(source_agent)[0]
        audited = extract_test_behaviors(source_audited)
        assert is_behavior_covered(agent, audited) is False

    def test_empty_audited_returns_not_covered(self) -> None:
        source_agent = "def test_anything(e):\n    pass\n"
        agent = extract_test_behaviors(source_agent)[0]
        assert is_behavior_covered(agent, []) is False
