"""Tests for TODO item 4: Card spec generator.

Tests verify:
- generate_card_spec returns dict with all required schema fields.
- Every field is non-null (except loyalty for non-planeswalkers, power/toughness for non-creatures).
- generate_all_specs creates one card_spec.json per card in the correct output path.
- Generated JSON is valid and parseable.
- Edge cases: planeswalker loyalty, creature power/toughness, non-creature null power/toughness.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from cards.registry import CardMetadata

REPO_ROOT = Path(__file__).resolve().parent.parent

# Schema fields per the TODO spec
REQUIRED_SCHEMA_FIELDS = {
    "name",
    "mana_cost",
    "type_line",
    "oracle_text",
    "power",
    "toughness",
    "loyalty",
    "colors",
    "keywords",
    "rarity",
    "set_code",
    "collector_number",
    "complexity_tier",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(**kwargs: object) -> CardMetadata:
    """Shorthand to create CardMetadata with sensible defaults."""
    defaults: dict[str, object] = {
        "name": "Test Card",
        "mana_cost_str": "{1}{W}",
        "type_line": "Creature — Human",
        "oracle_text": "First strike",
        "power": "2",
        "toughness": "2",
        "colors": ["W"],
        "keywords": ["First strike"],
        "rarity": "common",
        "set_code": "sos",
        "collector_number": "42",
    }
    defaults.update(kwargs)
    return CardMetadata(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# generate_card_spec — schema contract
# ---------------------------------------------------------------------------


class TestGenerateCardSpecSchema:
    """generate_card_spec must return a dict with all required schema fields."""

    def test_returns_dict(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card()
        result = generate_card_spec(card, "simple")
        assert isinstance(result, dict)

    def test_contains_all_schema_fields(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card()
        result = generate_card_spec(card, "medium")
        missing = REQUIRED_SCHEMA_FIELDS - result.keys()
        assert not missing, f"Missing schema fields: {missing}"

    def test_no_extra_fields(self) -> None:
        """Spec dict should only contain the defined schema fields."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card()
        result = generate_card_spec(card, "simple")
        extra = result.keys() - REQUIRED_SCHEMA_FIELDS
        assert not extra, f"Unexpected extra fields: {extra}"

    def test_complexity_tier_matches_input(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card()
        for tier in ("trivial", "simple", "medium", "complex", "expert"):
            result = generate_card_spec(card, tier)
            assert result["complexity_tier"] == tier


# ---------------------------------------------------------------------------
# generate_card_spec — field values
# ---------------------------------------------------------------------------


class TestGenerateCardSpecValues:
    """Field values are correctly mapped from CardMetadata."""

    def test_name_matches(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(name="Goblin Guide")
        result = generate_card_spec(card, "simple")
        assert result["name"] == "Goblin Guide"

    def test_mana_cost_matches(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(mana_cost_str="{2}{R}")
        result = generate_card_spec(card, "simple")
        assert result["mana_cost"] == "{2}{R}"

    def test_type_line_matches(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(type_line="Enchantment — Aura")
        result = generate_card_spec(card, "medium")
        assert result["type_line"] == "Enchantment — Aura"

    def test_colors_is_list(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(colors=["R", "G"])
        result = generate_card_spec(card, "simple")
        assert isinstance(result["colors"], list)
        assert result["colors"] == ["R", "G"]

    def test_keywords_is_list(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(keywords=["Flying", "Haste"])
        result = generate_card_spec(card, "simple")
        assert isinstance(result["keywords"], list)
        assert result["keywords"] == ["Flying", "Haste"]

    def test_set_code_matches(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(set_code="sos")
        result = generate_card_spec(card, "trivial")
        assert result["set_code"] == "sos"

    def test_collector_number_matches(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(collector_number="123")
        result = generate_card_spec(card, "trivial")
        assert result["collector_number"] == "123"


# ---------------------------------------------------------------------------
# Nullability rules
# ---------------------------------------------------------------------------


class TestNullabilityRules:
    """Verify nullable fields follow the spec rules."""

    def test_creature_has_non_null_power_toughness(self) -> None:
        """Creature cards must have non-null power and toughness."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card(
            type_line="Creature — Elf Warrior",
            power="3",
            toughness="2",
        )
        result = generate_card_spec(card, "simple")
        assert result["power"] is not None, "Creature power should not be null"
        assert result["toughness"] is not None, "Creature toughness should not be null"

    def test_non_creature_has_null_power_toughness(self) -> None:
        """Non-creature cards should have null power and toughness."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card(
            type_line="Instant",
            oracle_text="Draw two cards.",
            power=None,
            toughness=None,
        )
        result = generate_card_spec(card, "simple")
        assert result["power"] is None, "Non-creature power should be null"
        assert result["toughness"] is None, "Non-creature toughness should be null"

    def test_non_planeswalker_has_null_loyalty(self) -> None:
        """Non-planeswalker cards should have null loyalty."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card(type_line="Creature — Human")
        result = generate_card_spec(card, "simple")
        assert result["loyalty"] is None, "Non-planeswalker loyalty should be null"

    def test_creature_non_null_fields(self) -> None:
        """All non-nullable fields on a creature should be non-null."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card(
            name="Test Creature",
            mana_cost_str="{G}",
            type_line="Creature — Beast",
            oracle_text="Trample",
            power="4",
            toughness="4",
            colors=["G"],
            keywords=["Trample"],
            rarity="uncommon",
            set_code="sos",
            collector_number="77",
        )
        result = generate_card_spec(card, "simple")
        # Everything except loyalty should be non-null for a creature
        for field in REQUIRED_SCHEMA_FIELDS - {"loyalty"}:
            assert result[field] is not None, f"Field {field!r} should not be null for a creature"

    def test_instant_non_null_fields(self) -> None:
        """All non-nullable fields on an instant should be non-null (except power/toughness/loyalty)."""
        from benchmark.card_spec import generate_card_spec

        card = _make_card(
            name="Lightning Strike",
            mana_cost_str="{1}{R}",
            type_line="Instant",
            oracle_text="Deal 3 damage to any target.",
            power=None,
            toughness=None,
            colors=["R"],
            keywords=[],
            rarity="common",
            set_code="sos",
            collector_number="101",
        )
        result = generate_card_spec(card, "medium")
        for field in REQUIRED_SCHEMA_FIELDS - {"power", "toughness", "loyalty"}:
            assert result[field] is not None, f"Field {field!r} should not be null for an instant"


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


class TestSpecJsonSerialization:
    """Spec dicts must be valid JSON-serializable."""

    def test_spec_is_json_serializable(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card()
        spec = generate_card_spec(card, "simple")
        # Should not raise
        json_str = json.dumps(spec)
        assert isinstance(json_str, str)

    def test_spec_roundtrips_through_json(self) -> None:
        from benchmark.card_spec import generate_card_spec

        card = _make_card(
            name="Roundtrip Card",
            colors=["U", "B"],
            keywords=["Flying", "Deathtouch"],
        )
        spec = generate_card_spec(card, "complex")
        roundtripped = json.loads(json.dumps(spec))
        assert roundtripped == spec


# ---------------------------------------------------------------------------
# generate_all_specs — file output
# ---------------------------------------------------------------------------


class TestGenerateAllSpecs:
    """generate_all_specs creates per-card JSON files."""

    def test_creates_files_for_sos(self) -> None:
        """generate_all_specs should create at least one file for SOS set."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            assert len(written) > 0, "Should have generated at least one spec file"

    def test_each_file_is_named_card_spec_json(self) -> None:
        """Every output file should be named card_spec.json."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            for path in written:
                assert path.name == "card_spec.json", f"Expected card_spec.json, got {path.name}"

    def test_output_path_contains_collector_number(self) -> None:
        """Each file is in a directory named by collector_number."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            for path in written:
                # path = .../collector_number/card_spec.json
                collector_dir = path.parent.name
                assert collector_dir != "", "Collector number directory should not be empty"

    def test_each_file_is_valid_json(self) -> None:
        """Every generated file should contain valid parseable JSON."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            for path in written:
                text = path.read_text(encoding="utf-8")
                data = json.loads(text)  # Should not raise
                assert isinstance(data, dict), f"Expected dict in {path}, got {type(data)}"

    def test_each_file_has_all_schema_fields(self) -> None:
        """Every generated JSON file should have all schema fields."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            for path in written:
                data = json.loads(path.read_text(encoding="utf-8"))
                missing = REQUIRED_SCHEMA_FIELDS - data.keys()
                assert not missing, f"File {path} missing fields: {missing}"

    def test_one_file_per_card(self) -> None:
        """Number of files should match number of cards in SOS data."""
        from benchmark.card_spec import generate_all_specs

        sos_data_path = REPO_ROOT / "benchmarks" / "sos" / "data" / "sos.json"
        with open(sos_data_path, encoding="utf-8") as f:
            sos_cards = json.load(f)

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            assert len(written) == len(sos_cards), (
                f"Expected {len(sos_cards)} files, got {len(written)}"
            )


# ---------------------------------------------------------------------------
# SOS integration: nullability rules per card type
# ---------------------------------------------------------------------------


class TestSOSSpecNullability:
    """Validate nullability rules across all real SOS card specs."""

    @pytest.fixture()
    def sos_specs(self) -> list[dict]:
        """Generate all SOS specs and return the parsed dicts."""
        from benchmark.card_spec import generate_all_specs

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(REPO_ROOT)
            try:
                written = generate_all_specs("sos", tmpdir)
            finally:
                os.chdir(old_cwd)

            specs = []
            for path in written:
                specs.append(json.loads(path.read_text(encoding="utf-8")))
            return specs

    def test_creatures_have_power_toughness(self, sos_specs: list[dict]) -> None:
        """Every creature in SOS should have non-null power and toughness."""
        creatures = [s for s in sos_specs if "Creature" in s.get("type_line", "")]
        assert len(creatures) > 0, "SOS should have at least one creature"
        for spec in creatures:
            assert spec["power"] is not None, (
                f"Creature {spec['name']!r} has null power"
            )
            assert spec["toughness"] is not None, (
                f"Creature {spec['name']!r} has null toughness"
            )

    def test_non_creatures_have_null_power_toughness(self, sos_specs: list[dict]) -> None:
        """Non-creature, non-vehicle cards should have null power and toughness.

        Vehicles have power/toughness despite not being Creatures on their
        type line, so they are excluded from this check.
        """
        non_creatures = [
            s for s in sos_specs
            if "Creature" not in s.get("type_line", "")
            and "Vehicle" not in s.get("type_line", "")
        ]
        assert len(non_creatures) > 0, "SOS should have non-creature, non-vehicle cards"
        for spec in non_creatures:
            assert spec["power"] is None, (
                f"Non-creature {spec['name']!r} has non-null power: {spec['power']!r}"
            )
            assert spec["toughness"] is None, (
                f"Non-creature {spec['name']!r} has non-null toughness: {spec['toughness']!r}"
            )

    def test_planeswalkers_have_loyalty(self, sos_specs: list[dict]) -> None:
        """Planeswalker cards should have non-null loyalty."""
        pws = [s for s in sos_specs if "Planeswalker" in s.get("type_line", "")]
        # SOS may not have planeswalkers; skip if none
        if len(pws) == 0:
            pytest.skip("No planeswalkers in SOS set")
        for spec in pws:
            assert spec["loyalty"] is not None, (
                f"Planeswalker {spec['name']!r} has null loyalty"
            )

    def test_non_planeswalkers_have_null_loyalty(self, sos_specs: list[dict]) -> None:
        """Non-planeswalker cards should have null loyalty."""
        non_pws = [s for s in sos_specs if "Planeswalker" not in s.get("type_line", "")]
        assert len(non_pws) > 0
        for spec in non_pws:
            assert spec["loyalty"] is None, (
                f"Non-planeswalker {spec['name']!r} has non-null loyalty: {spec['loyalty']!r}"
            )

    def test_all_common_fields_non_null(self, sos_specs: list[dict]) -> None:
        """Fields that should always be non-null: name, mana_cost, type_line, etc."""
        always_non_null = {"name", "type_line", "colors", "keywords", "rarity",
                           "set_code", "collector_number", "complexity_tier"}
        for spec in sos_specs:
            for field in always_non_null:
                assert spec[field] is not None, (
                    f"Card {spec.get('name', '?')!r} has null {field!r}"
                )
