"""Credential scan compatibility retained across candidate format versions."""

import json
from pathlib import Path

import pytest

from silverquillm.candidate import redact_credentials, scan_tree_for_credentials
from tests.candidate_fixtures import SLOT_ASSIGNMENTS, SLOT_MENTIONS


class TestDeclaredSlotAssignment:
    """A declared slot used as an assignment key with any non-empty value is
    a secret value — whatever its length, its characters or its quoting; the
    slot merely *named* (declared in a list, mentioned in prose, assigned
    nothing) is not.  One shared shape serves the tree scan and the
    redactor, and neither ever surfaces the value."""

    SLOTS = ("ANTHROPIC_API_KEY",)
    PLACEHOLDER = "[redacted: a value assigned to secret slot ANTHROPIC_API_KEY]"

    @pytest.mark.parametrize("form", sorted(SLOT_ASSIGNMENTS))
    def test_an_assignment_of_any_shape_is_found_by_path_and_shape_only(
        self, tmp_path: Path, form: str
    ) -> None:
        line = SLOT_ASSIGNMENTS[form]
        (tmp_path / "notes.txt").write_text(f"# notes\n{line}\ntrailing line\n", encoding="utf-8")
        findings = scan_tree_for_credentials(tmp_path, secret_slots=self.SLOTS)
        assert [str(finding) for finding in findings] == [
            "notes.txt: a value assigned to secret slot ANTHROPIC_API_KEY"
        ]

    @pytest.mark.parametrize("form", sorted(SLOT_ASSIGNMENTS))
    def test_an_assignment_of_any_shape_is_redacted_whole(self, form: str) -> None:
        line = SLOT_ASSIGNMENTS[form]
        assert (
            redact_credentials(f"provider said: {line}", secret_slots=self.SLOTS)
            == f"provider said: {self.PLACEHOLDER}"
        )

    @pytest.mark.parametrize("form", sorted(SLOT_MENTIONS))
    def test_a_declaration_a_mention_or_an_empty_assignment_is_left_alone(
        self, tmp_path: Path, form: str
    ) -> None:
        line = SLOT_MENTIONS[form]
        (tmp_path / "notes.txt").write_text(f"# notes\n{line}\n", encoding="utf-8")
        assert scan_tree_for_credentials(tmp_path, secret_slots=self.SLOTS) == []
        assert redact_credentials(f"note: {line}", secret_slots=self.SLOTS) == f"note: {line}"

    @pytest.mark.parametrize("line", [*SLOT_ASSIGNMENTS.values(), *SLOT_MENTIONS.values()])
    def test_the_tree_scan_and_the_redactor_agree(self, tmp_path: Path, line: str) -> None:
        (tmp_path / "f").write_text(line + "\n", encoding="utf-8")
        found = bool(scan_tree_for_credentials(tmp_path, secret_slots=self.SLOTS))
        assert found == (redact_credentials(line, secret_slots=self.SLOTS) != line)

    def test_a_bare_value_is_blanked_to_its_line_end_and_a_quoted_one_to_its_quote(self) -> None:
        text = 'ANTHROPIC_API_KEY=abc def # comment\nnext line\nANTHROPIC_API_KEY="q" tail'
        assert (
            redact_credentials(text, secret_slots=self.SLOTS)
            == f"{self.PLACEHOLDER}\nnext line\n{self.PLACEHOLDER} tail"
        )

    def test_only_a_declared_slot_is_an_assignment_key(self) -> None:
        text = "OTHER_KEY=value; ANTHROPIC_API_KEY=value"
        assert redact_credentials(text, secret_slots=()) == text
        assert (
            redact_credentials(text, secret_slots=self.SLOTS)
            == f"OTHER_KEY=value; {self.PLACEHOLDER}"
        )

    def test_a_serialized_value_holding_an_escaped_quote_is_redacted_whole(
        self, tmp_path: Path
    ) -> None:
        """A JSON serializer writes a value that contains a quote as ``\\"``.
        The string closes only at the unescaped quote, so the tree scan finds
        the pair and the redactor blanks it whole — neither the fragment
        before the escape nor the one after it survives — while the field
        after the correctly closed scalar is left alone."""
        document = json.dumps({"ANTHROPIC_API_KEY": 'left7"right9', "other": "keep"})
        assert '\\"' in document
        (tmp_path / "config.json").write_text(document + "\n", encoding="utf-8")
        findings = scan_tree_for_credentials(tmp_path, secret_slots=self.SLOTS)
        assert [str(finding) for finding in findings] == [
            "config.json: a value assigned to secret slot ANTHROPIC_API_KEY"
        ]
        redacted = redact_credentials(document, secret_slots=self.SLOTS)
        assert redacted == f'{{{self.PLACEHOLDER}, "other": "keep"}}'
        assert "left7" not in redacted and "right9" not in redacted

    def test_an_escaped_backslash_before_the_closing_quote_still_closes_the_string(self) -> None:
        document = json.dumps({"ANTHROPIC_API_KEY": "tail\\", "other": "keep"})
        assert document.endswith('\\\\", "other": "keep"}')
        assert (
            redact_credentials(document, secret_slots=self.SLOTS)
            == f'{{{self.PLACEHOLDER}, "other": "keep"}}'
        )

    def test_a_quote_that_never_closes_falls_through_to_the_bare_form(self) -> None:
        """An escaped quote with no closing quote after it, and a YAML doubled
        single quote, leave the string open; the bare form then takes the
        line to its end, so the whole line goes rather than a fragment."""
        for line in ('ANTHROPIC_API_KEY="left7\\"right9', "ANTHROPIC_API_KEY: 'it''s' # note"):
            assert (
                redact_credentials(f"{line}\nnext", secret_slots=self.SLOTS)
                == f"{self.PLACEHOLDER}\nnext"
            ), line


def test_historical_golden_candidate_hash_is_unchanged():
    from silverquillm.results_repo import CandidateIdentity, candidate_hash

    vectors = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/specs/bench-identity-vectors.json").read_text()
    )
    hashes = []
    for vector in vectors["vectors"]:
        expected = vector["expected"]["identity_triple"]
        identity = CandidateIdentity.recomputed(
            expected["base_digest"], expected["instruction_hash"], expected["adapter"]
        )
        hashes.append(candidate_hash(identity))
    assert hashes[0] == "74e6198d8500024a1d8df060c9a2e6906011fc7dd6e5a23d7d4d66e194895f96"
    assert len(set(hashes)) == len(hashes)
