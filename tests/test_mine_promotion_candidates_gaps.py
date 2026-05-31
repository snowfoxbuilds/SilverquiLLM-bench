"""Gap tests for scripts/mine_promotion_candidates.py.

Covers gaps NOT already tested in test_mine_promotion_candidates.py:
- Empty agent tests.py (no test functions) → zero candidates, no crash.
- Empty-engine-API Jaccard edge: both tests have no API calls → _jaccard({},{})=0.0,
  no ZeroDivisionError, Rule 2 does not wrongly auto-suppress.
- Class-based test methods detected end-to-end through mine_candidates.
- Audited file has a test fn the agent did NOT write → no spurious candidate.
- --format json output contains ALL Candidate dataclass fields.
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
# Reuse already-loaded module if present (avoids duplicate-load issues when
# both test files are collected in the same pytest session).
if "mine_promotion_candidates" not in sys.modules:
    sys.modules["mine_promotion_candidates"] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules["mine_promotion_candidates"]

mine_candidates = _mod.mine_candidates
Candidate = _mod.Candidate
extract_test_behaviors = _mod.extract_test_behaviors
is_behavior_covered = _mod.is_behavior_covered
format_candidates_json = _mod.format_candidates_json
main = _mod.main
_jaccard = _mod._jaccard


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors the ones in the Tester's file)
# ---------------------------------------------------------------------------


def _write_agent_tests(root: Path, image: str, run: str, card: str, source: str) -> Path:
    d = root / "docker" / image / "validated_results" / run / "cards" / card
    d.mkdir(parents=True, exist_ok=True)
    f = d / "tests.py"
    f.write_text(textwrap.dedent(source))
    return f


def _write_audited_tests(
    root: Path, card: str, source: str, bench: str = "sos"
) -> Path:
    d = root / "benchmarks" / bench / "data" / "tests" / "audited" / bench / card
    d.mkdir(parents=True, exist_ok=True)
    f = d / "tests.py"
    f.write_text(textwrap.dedent(source))
    return f


# ---------------------------------------------------------------------------
# Gap 1: empty agent tests.py (exists but has no test functions)
# ---------------------------------------------------------------------------


class TestEmptyAgentTestsFile:
    """An agent tests.py that exists but defines no test_* functions → zero
    candidates, no crash."""

    def test_empty_file_yields_no_candidates(self, tmp_path: Path) -> None:
        # Create an agent tests.py with no test functions at all.
        _write_agent_tests(tmp_path, "imgA", "run1", "sos_900", "# no tests here\n")

        candidates = mine_candidates(tmp_path)
        assert candidates == []

    def test_file_with_only_helper_functions_yields_no_candidates(
        self, tmp_path: Path
    ) -> None:
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_901",
            """\
                def helper():
                    return 42

                def setup_fixture():
                    pass
            """,
        )

        candidates = mine_candidates(tmp_path)
        assert candidates == []

    def test_empty_file_with_audited_baseline_yields_no_candidates(
        self, tmp_path: Path
    ) -> None:
        _write_audited_tests(
            tmp_path,
            "sos_902",
            """\
                def test_something(engine):
                    pass
            """,
        )
        _write_agent_tests(
            tmp_path, "imgA", "run1", "sos_902", "# empty agent tests\n"
        )

        candidates = mine_candidates(tmp_path)
        assert candidates == []


# ---------------------------------------------------------------------------
# Gap 2: empty-engine-API Jaccard edge — no ZeroDivisionError, no wrong suppression
# ---------------------------------------------------------------------------


class TestEmptyEngineApiJaccardEdge:
    """When both agent and audited tests reference zero engine APIs, _jaccard
    returns 0.0 (not a ZeroDivisionError) and Rule 2 does NOT suppress the
    candidate."""

    def test_jaccard_both_empty_returns_zero(self) -> None:
        result = _jaccard(frozenset(), frozenset())
        assert result == 0.0

    def test_both_empty_apis_does_not_auto_suppress(self, tmp_path: Path) -> None:
        """Agent and audited tests with no API calls: Rule 2 cannot fire (Jaccard=0.0
        < 0.8); different names → agent IS surfaced as a candidate."""
        _write_audited_tests(
            tmp_path,
            "sos_910",
            """\
                def test_something_audited():
                    \"\"\"Check basic behavior.\"\"\"
                    assert True
            """,
        )
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_910",
            """\
                def test_different_agent():
                    \"\"\"Check basic behavior.\"\"\"
                    assert True
            """,
        )

        # Different name, no engine APIs on either side → Jaccard(∅,∅)=0.0 → Rule 2
        # does not fire → agent test IS a candidate (novel name, not covered).
        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].test_name == "test_different_agent"

    def test_is_behavior_covered_both_empty_apis_different_name(self) -> None:
        """is_behavior_covered unit-level: different name, no APIs on either side
        → not covered (no ZeroDivisionError)."""
        agent_src = "def test_alpha():\n    \"\"\"some keyword here.\"\"\"\n    assert True\n"
        audited_src = "def test_beta():\n    \"\"\"some keyword here.\"\"\"\n    assert True\n"
        agent = extract_test_behaviors(agent_src)[0]
        audited = extract_test_behaviors(audited_src)
        # Must not raise, must return False (different name, Jaccard=0.0 < 0.8)
        assert is_behavior_covered(agent, audited) is False


# ---------------------------------------------------------------------------
# Gap 3: class-based test methods detected via mine_candidates (integration)
# ---------------------------------------------------------------------------


class TestClassBasedMethodsEndToEnd:
    """Methods inside a class TestX: are detected by mine_candidates, not just
    by extract_test_behaviors at the unit level."""

    def test_class_test_method_surfaced_as_candidate(self, tmp_path: Path) -> None:
        # No audited file → everything is a candidate.
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_920",
            """\
                class TestCardAbilities:
                    def test_flying_keyword(self, engine):
                        \"\"\"Verify flying keyword.\"\"\"
                        assert engine.has_ability("flying")
            """,
        )

        candidates = mine_candidates(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].test_name == "test_flying_keyword"
        assert candidates[0].note == "no audited baseline"

    def test_class_test_method_suppressed_by_name_match(self, tmp_path: Path) -> None:
        """A class-based agent test whose normalized name matches an audited test
        (top-level) is correctly suppressed."""
        _write_audited_tests(
            tmp_path,
            "sos_921",
            """\
                def test_flying_keyword(engine):
                    \"\"\"Verify flying keyword.\"\"\"
                    pass
            """,
        )
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_921",
            """\
                class TestCardAbilities:
                    def test_flying_keyword(self, engine):
                        \"\"\"Verify flying keyword.\"\"\"
                        pass
            """,
        )

        candidates = mine_candidates(tmp_path)
        assert candidates == []


# ---------------------------------------------------------------------------
# Gap 4: audited has a test fn the agent did NOT write → no spurious candidate
# ---------------------------------------------------------------------------


class TestNoSpuriousCandidateFromAuditedOnly:
    """When the agent tests.py covers the same behaviors as the audited file
    (by name) the miner emits no spurious candidates.  Conversely, behaviors
    present ONLY in the audited file (and absent from the agent file) must NOT
    appear as candidates."""

    def test_audited_only_test_does_not_produce_candidate(
        self, tmp_path: Path
    ) -> None:
        # Audited has two tests; agent only has one (matching the first).
        _write_audited_tests(
            tmp_path,
            "sos_930",
            """\
                def test_alpha(engine):
                    pass

                def test_beta(engine):
                    pass
            """,
        )
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_930",
            """\
                def test_alpha(engine):
                    pass
            """,
        )

        # Agent only wrote test_alpha which matches the audited test_alpha.
        # test_beta exists only in the audited file and must NOT appear as a candidate.
        candidates = mine_candidates(tmp_path)
        assert candidates == []

    def test_agent_subset_of_audited_no_candidates(self, tmp_path: Path) -> None:
        """All agent behaviors are covered → zero candidates, even when audited
        has additional tests."""
        _write_audited_tests(
            tmp_path,
            "sos_931",
            """\
                def test_creature_type(engine):
                    pass
                def test_mana_cost(engine):
                    pass
                def test_power_toughness(engine):
                    pass
            """,
        )
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_931",
            """\
                def test_creature_type(engine):
                    pass
                def test_mana_cost(engine):
                    pass
            """,
        )

        candidates = mine_candidates(tmp_path)
        assert candidates == []


# ---------------------------------------------------------------------------
# Gap 5: --format json output contains ALL Candidate dataclass fields
# ---------------------------------------------------------------------------


class TestJsonFormatAllFields:
    """format_candidates_json produces valid JSON with every Candidate field."""

    # Candidate fields: card, image, run, test_name, normalized_name,
    # docstring, engine_apis, source_snippet, note

    _EXPECTED_FIELDS = {
        "card",
        "image",
        "run",
        "test_name",
        "normalized_name",
        "docstring",
        "engine_apis",
        "source_snippet",
        "note",
    }

    def test_json_format_contains_all_candidate_fields(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_agent_tests(
            tmp_path,
            "imgA",
            "run1",
            "sos_940",
            """\
                def test_full_fields(engine):
                    \"\"\"A test with a docstring.\"\"\"
                    card = engine.create_card("X")
                    assert card.power == 2
            """,
        )

        with mock.patch(
            "sys.argv", ["mine_promotion_candidates.py", "--format", "json"]
        ):
            main(repo_root=tmp_path)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        record = data[0]
        assert self._EXPECTED_FIELDS == set(record.keys())

    def test_json_format_field_values_correct(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_agent_tests(
            tmp_path,
            "imgZ",
            "runQ",
            "sos_941",
            """\
                def test_field_values(engine):
                    \"\"\"Docstring for field check.\"\"\"
                    card = engine.get_card()
                    assert card.toughness == 1
            """,
        )

        with mock.patch(
            "sys.argv", ["mine_promotion_candidates.py", "--format", "json"]
        ):
            main(repo_root=tmp_path)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        r = data[0]

        assert r["card"] == "sos_941"
        assert r["image"] == "imgZ"
        assert r["run"] == "runQ"
        assert r["test_name"] == "test_field_values"
        assert r["normalized_name"] == "field_values"
        assert "Docstring for field check" in r["docstring"]
        assert isinstance(r["engine_apis"], list)
        assert r["source_snippet"]  # non-empty
        assert r["note"] == "no audited baseline"

    def test_format_candidates_json_direct_call(self) -> None:
        """format_candidates_json on a hand-built Candidate emits valid JSON with
        all fields."""
        c = Candidate(
            card="sos_942",
            image="imgA",
            run="run1",
            test_name="test_something",
            normalized_name="something",
            docstring="Does something useful.",
            engine_apis=["create_card", "power"],
            source_snippet="def test_something(e):\n    pass",
            note="no audited baseline",
        )
        raw = format_candidates_json([c])
        data = json.loads(raw)
        assert len(data) == 1
        record = data[0]
        assert record["card"] == "sos_942"
        assert record["engine_apis"] == ["create_card", "power"]
        assert record["note"] == "no audited baseline"
        assert set(record.keys()) == {
            "card", "image", "run", "test_name", "normalized_name",
            "docstring", "engine_apis", "source_snippet", "note",
        }
