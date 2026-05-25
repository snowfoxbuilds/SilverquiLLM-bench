"""Tests for engine/types.py — core enums and type definitions.

Verifies:
- All enum members exist with correct names and values.
- Color single-letter aliases (W, U, B, R, G) resolve to the full-name members.
- Keyword is a proper Flag enum supporting bitwise composition and membership.
- ManaCost dataclass: construction, cmc property, and parse() classmethod.
- ManaCost.parse covers generic, colored, X costs, mixed, and invalid inputs.
- TargetRequirement dataclass can be instantiated with expected fields.
"""

from __future__ import annotations

import enum

import pytest

from benchmarks.sos.workspace.engine.types import (
    CardType,
    Color,
    HybridManaSymbol,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    TargetRequirement,
    Zone,
)


# ---------------------------------------------------------------------------
# Color enum
# ---------------------------------------------------------------------------
class TestColor:
    """Verify Color enum members and single-letter aliases."""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("WHITE", "W"),
            ("BLUE", "U"),
            ("BLACK", "B"),
            ("RED", "R"),
            ("GREEN", "G"),
        ],
        ids=["WHITE", "BLUE", "BLACK", "RED", "GREEN"],
    )
    def test_member_exists_with_correct_value(self, name: str, value: str) -> None:
        """Each Color member must exist and map to its single-letter value."""
        member = Color[name]
        assert member.value == value

    def test_exactly_five_members(self) -> None:
        """Color enum should have exactly 5 members."""
        assert len(Color) == 5

    @pytest.mark.parametrize(
        "alias,expected_member",
        [
            ("W", "WHITE"),
            ("U", "BLUE"),
            ("B", "BLACK"),
            ("R", "RED"),
            ("G", "GREEN"),
        ],
        ids=["W->WHITE", "U->BLUE", "B->BLACK", "R->RED", "G->GREEN"],
    )
    def test_single_letter_alias_resolves(self, alias: str, expected_member: str) -> None:
        """Color.W, Color.U, etc. must resolve to the corresponding full member."""
        alias_value = getattr(Color, alias)
        assert alias_value is Color[expected_member]


# ---------------------------------------------------------------------------
# ManaType enum
# ---------------------------------------------------------------------------
class TestManaType:
    """Verify ManaType enum members."""

    EXPECTED_MEMBERS = {
        "WHITE": "W",
        "BLUE": "U",
        "BLACK": "B",
        "RED": "R",
        "GREEN": "G",
        "COLORLESS": "C",
    }

    @pytest.mark.parametrize(
        "name,value",
        list(EXPECTED_MEMBERS.items()),
        ids=list(EXPECTED_MEMBERS.keys()),
    )
    def test_member_exists_with_correct_value(self, name: str, value: str) -> None:
        member = ManaType[name]
        assert member.value == value

    def test_exactly_six_members(self) -> None:
        """ManaType should include the 5 colors plus COLORLESS."""
        assert len(ManaType) == 6


# ---------------------------------------------------------------------------
# Zone enum
# ---------------------------------------------------------------------------
class TestZone:
    """Verify Zone enum members."""

    EXPECTED = [
        "BATTLEFIELD", "HAND", "LIBRARY", "GRAVEYARD", "EXILE", "STACK", "COMMAND",
    ]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name: str) -> None:
        assert name in Zone.__members__

    def test_exactly_seven_members(self) -> None:
        assert len(Zone) == 7


# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------
class TestPhase:
    """Verify Phase enum members."""

    EXPECTED = [
        "BEGINNING", "PRECOMBAT_MAIN", "COMBAT", "POSTCOMBAT_MAIN", "ENDING",
    ]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name: str) -> None:
        assert name in Phase.__members__

    def test_exactly_five_members(self) -> None:
        assert len(Phase) == 5


# ---------------------------------------------------------------------------
# Step enum
# ---------------------------------------------------------------------------
class TestStep:
    """Verify Step enum members."""

    EXPECTED = [
        "UNTAP", "UPKEEP", "DRAW",
        "BEGIN_COMBAT", "DECLARE_ATTACKERS", "DECLARE_BLOCKERS",
        "COMBAT_DAMAGE", "END_COMBAT",
        "END", "CLEANUP",
    ]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name: str) -> None:
        assert name in Step.__members__

    def test_exactly_ten_members(self) -> None:
        assert len(Step) == 10

    def test_none_is_valid_for_main_phase_steps(self) -> None:
        """The spec says Step is None for main phases; verify None is a valid value."""
        # Step itself doesn't include None as a member, but the type annotation
        # for step-in-phase should allow Optional[Step]. We just verify that
        # None is not in Step members (it shouldn't be an enum member).
        assert "NONE" not in Step.__members__


# ---------------------------------------------------------------------------
# CardType enum
# ---------------------------------------------------------------------------
class TestCardType:
    """Verify CardType enum members."""

    EXPECTED = [
        "CREATURE", "INSTANT", "SORCERY", "ENCHANTMENT",
        "ARTIFACT", "PLANESWALKER", "LAND",
    ]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name: str) -> None:
        assert name in CardType.__members__

    def test_exactly_seven_members(self) -> None:
        assert len(CardType) == 7


# ---------------------------------------------------------------------------
# Supertype enum
# ---------------------------------------------------------------------------
class TestSupertype:
    """Verify Supertype enum members."""

    EXPECTED = ["BASIC", "LEGENDARY", "SNOW"]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name: str) -> None:
        assert name in Supertype.__members__

    def test_exactly_three_members(self) -> None:
        assert len(Supertype) == 3


# ---------------------------------------------------------------------------
# Keyword Flag enum
# ---------------------------------------------------------------------------
class TestKeyword:
    """Verify Keyword is a Flag enum with all expected evergreen keywords."""

    ALL_KEYWORDS = [
        "FLYING", "FIRST_STRIKE", "DOUBLE_STRIKE", "DEATHTOUCH",
        "TRAMPLE", "LIFELINK", "VIGILANCE", "REACH", "HASTE",
        "FLASH", "DEFENDER", "HEXPROOF", "INDESTRUCTIBLE", "MENACE", "WARD",
    ]

    def test_is_flag_enum(self) -> None:
        """Keyword must be an enum.Flag subclass to support bitwise composition."""
        assert issubclass(Keyword, enum.Flag)

    @pytest.mark.parametrize("name", ALL_KEYWORDS)
    def test_member_exists(self, name: str) -> None:
        assert name in Keyword.__members__

    def test_exactly_sixteen_members(self) -> None:
        assert len(Keyword) == 16

    def test_bitwise_or_composition(self) -> None:
        """Combining keywords with | should produce a valid Keyword flag value."""
        combined = Keyword.FLYING | Keyword.TRAMPLE
        assert isinstance(combined, Keyword)

    def test_membership_in_combined_flag(self) -> None:
        """Individual keywords should be detectable in a combined flag via `in`."""
        combined = Keyword.FLYING | Keyword.TRAMPLE | Keyword.LIFELINK
        assert Keyword.FLYING in combined
        assert Keyword.TRAMPLE in combined
        assert Keyword.LIFELINK in combined
        assert Keyword.HASTE not in combined

    def test_combining_all_keywords(self) -> None:
        """All 15 keywords ORed together should still be a valid Keyword."""
        combined = Keyword(0)
        for kw in Keyword:
            combined = combined | kw
        for kw in Keyword:
            assert kw in combined

    def test_each_keyword_has_distinct_value(self) -> None:
        """Every keyword should have a unique power-of-two value."""
        values = [kw.value for kw in Keyword]
        assert len(values) == len(set(values)), "Keyword values must be distinct"
        for v in values:
            assert v != 0 and (v & (v - 1)) == 0, f"{v} is not a power of two"


# ---------------------------------------------------------------------------
# ManaCost dataclass
# ---------------------------------------------------------------------------
class TestManaCostConstruction:
    """Verify ManaCost dataclass construction and defaults."""

    def test_default_values(self) -> None:
        """ManaCost() should default to generic=0, empty pips, x_count=0."""
        mc = ManaCost()
        assert mc.generic == 0
        assert mc.pips == {}
        assert mc.x_count == 0

    def test_immutable_frozen(self) -> None:
        """ManaCost should be frozen (immutable)."""
        mc = ManaCost(generic=3)
        with pytest.raises(AttributeError):
            mc.generic = 5  # type: ignore[misc]


class TestManaCostCmc:
    """Verify ManaCost.cmc property calculations."""

    def test_cmc_generic_only(self) -> None:
        """CMC of generic-only cost should equal the generic amount."""
        mc = ManaCost(generic=5)
        assert mc.cmc == 5

    def test_cmc_colored_only(self) -> None:
        """CMC of colored-only cost should equal the number of pips."""
        mc = ManaCost(pips={ManaType.WHITE: 1, ManaType.BLUE: 1})
        assert mc.cmc == 2

    def test_cmc_mixed_generic_and_colored(self) -> None:
        """CMC should sum generic and all pip counts."""
        mc = ManaCost(generic=2, pips={ManaType.WHITE: 1, ManaType.BLUE: 1})
        assert mc.cmc == 4

    def test_cmc_x_cost_treated_as_zero(self) -> None:
        """X costs contribute 0 to CMC."""
        mc = ManaCost(generic=0, pips={ManaType.RED: 1}, x_count=2)
        assert mc.cmc == 1

    def test_cmc_zero_cost(self) -> None:
        """A zero-cost card has cmc 0."""
        mc = ManaCost(generic=0, pips={})
        assert mc.cmc == 0


class TestManaCostParse:
    """Verify ManaCost.parse classmethod with various valid inputs."""

    def test_parse_generic_only(self) -> None:
        """'{2}' → generic=2, no pips."""
        mc = ManaCost.parse("{2}")
        assert mc.generic == 2
        assert mc.pips == {}
        assert mc.x_count == 0
        assert mc.cmc == 2

    def test_parse_colored_only(self) -> None:
        """'{W}{U}' → 1 white pip + 1 blue pip."""
        mc = ManaCost.parse("{W}{U}")
        assert mc.generic == 0
        assert mc.pips[ManaType.WHITE] == 1
        assert mc.pips[ManaType.BLUE] == 1
        assert mc.cmc == 2

    def test_parse_mixed_generic_and_colored(self) -> None:
        """'{2}{W}{U}' → generic=2, 1 white, 1 blue, cmc=4."""
        mc = ManaCost.parse("{2}{W}{U}")
        assert mc.generic == 2
        assert mc.pips[ManaType.WHITE] == 1
        assert mc.pips[ManaType.BLUE] == 1
        assert mc.cmc == 4

    def test_parse_single_color(self) -> None:
        """'{B}' → 1 black pip, cmc=1."""
        mc = ManaCost.parse("{B}")
        assert mc.generic == 0
        assert mc.pips[ManaType.BLACK] == 1
        assert mc.cmc == 1

    def test_parse_x_cost(self) -> None:
        """'{X}{R}' → x_count=1, 1 red pip, cmc=1 (X treated as 0)."""
        mc = ManaCost.parse("{X}{R}")
        assert mc.x_count == 1
        assert mc.pips[ManaType.RED] == 1
        assert mc.cmc == 1

    def test_parse_double_x(self) -> None:
        """'{X}{X}' → x_count=2, cmc=0."""
        mc = ManaCost.parse("{X}{X}")
        assert mc.x_count == 2
        assert mc.pips == {}
        assert mc.generic == 0
        assert mc.cmc == 0

    def test_parse_zero(self) -> None:
        """'{0}' → generic=0, no pips, cmc=0."""
        mc = ManaCost.parse("{0}")
        assert mc.generic == 0
        assert mc.pips == {}
        assert mc.cmc == 0

    def test_parse_multiple_same_color(self) -> None:
        """'{R}{R}{R}' → 3 red pips, cmc=3."""
        mc = ManaCost.parse("{R}{R}{R}")
        assert mc.pips[ManaType.RED] == 3
        assert mc.cmc == 3

    def test_parse_all_five_colors(self) -> None:
        """'{W}{U}{B}{R}{G}' → one pip of each color, cmc=5."""
        mc = ManaCost.parse("{W}{U}{B}{R}{G}")
        assert mc.pips[ManaType.WHITE] == 1
        assert mc.pips[ManaType.BLUE] == 1
        assert mc.pips[ManaType.BLACK] == 1
        assert mc.pips[ManaType.RED] == 1
        assert mc.pips[ManaType.GREEN] == 1
        assert mc.cmc == 5

    def test_parse_large_generic(self) -> None:
        """'{15}' → generic=15, cmc=15."""
        mc = ManaCost.parse("{15}")
        assert mc.generic == 15
        assert mc.cmc == 15

    def test_parse_colorless_pip(self) -> None:
        """'{C}' should parse as a colorless pip, not generic mana."""
        mc = ManaCost.parse("{C}")
        assert mc.pips[ManaType.COLORLESS] == 1
        assert mc.generic == 0
        assert mc.cmc == 1

    def test_parse_complex_cost(self) -> None:
        """'{X}{3}{B}{B}{G}' → x_count=1, generic=3, 2 black + 1 green, cmc=6."""
        mc = ManaCost.parse("{X}{3}{B}{B}{G}")
        assert mc.x_count == 1
        assert mc.generic == 3
        assert mc.pips[ManaType.BLACK] == 2
        assert mc.pips[ManaType.GREEN] == 1
        assert mc.cmc == 6


class TestManaCostParseInvalid:
    """Verify ManaCost.parse raises ValueError on invalid inputs."""

    def test_empty_string_raises(self) -> None:
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only string should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("   ")

    def test_no_braces_raises(self) -> None:
        """String without braces (e.g., '2WU') should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("2WU")

    def test_unrecognised_symbol_raises(self) -> None:
        """An unknown symbol like {Z} should raise ValueError."""
        with pytest.raises(ValueError, match="[Uu]nrecogni"):
            ManaCost.parse("{Z}")

    # --- Malformed-but-tokenizable edge cases (reviewer-requested) ----------

    def test_trailing_junk_after_valid_tokens_raises(self) -> None:
        """'{W}{U}junk' has extra characters outside braces and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("{W}{U}junk")

    def test_space_between_tokens_raises(self) -> None:
        """'{2} {G}' has a space between tokens and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("{2} {G}")

    def test_negative_generic_mana_raises(self) -> None:
        """'{-1}' contains a negative number and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("{-1}")

    def test_leading_junk_before_valid_tokens_raises(self) -> None:
        """'abc{W}' has extra characters before the first brace and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("abc{W}")

    def test_junk_between_tokens_raises(self) -> None:
        """'{W}abc{U}' has extra characters between valid tokens and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("{W}abc{U}")

    def test_negative_generic_with_colored_pip_raises(self) -> None:
        """'{-3}{R}' contains a negative generic cost and should raise ValueError."""
        with pytest.raises(ValueError):
            ManaCost.parse("{-3}{R}")


# ---------------------------------------------------------------------------
# TargetRequirement dataclass
# ---------------------------------------------------------------------------
class TestTargetRequirement:
    """Verify TargetRequirement dataclass instantiation and field access."""

    def test_basic_instantiation(self) -> None:
        """TargetRequirement should store filter_fn, description, and zone."""
        predicate = lambda obj: True  # noqa: E731
        tr = TargetRequirement(
            filter_fn=predicate,
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )
        assert tr.filter_fn is predicate
        assert tr.description == "target creature"
        assert tr.zone is Zone.BATTLEFIELD

    def test_filter_fn_is_callable(self) -> None:
        """The filter_fn should be callable."""
        tr = TargetRequirement(
            filter_fn=lambda x: x is not None,
            description="any target",
            zone=Zone.GRAVEYARD,
        )
        assert callable(tr.filter_fn)
        assert tr.filter_fn("something") is True

    def test_zone_is_zone_enum(self) -> None:
        """The zone field should accept and store a Zone enum value."""
        tr = TargetRequirement(
            filter_fn=lambda x: True,
            description="exile target",
            zone=Zone.EXILE,
        )
        assert isinstance(tr.zone, Zone)
        assert tr.zone is Zone.EXILE
