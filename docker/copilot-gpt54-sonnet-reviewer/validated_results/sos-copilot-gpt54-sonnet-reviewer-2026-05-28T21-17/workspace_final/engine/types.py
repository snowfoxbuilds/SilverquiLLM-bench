"""Core enums and type definitions for the SilverquiLLM engine."""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any, Callable


class Color(enum.Enum):
    """The five colors of Magic."""

    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"


# Single-letter aliases accessible as Color.W, Color.U, etc.
Color.W = Color.WHITE  # type: ignore[attr-defined]
Color.U = Color.BLUE  # type: ignore[attr-defined]
Color.B = Color.BLACK  # type: ignore[attr-defined]
Color.R = Color.RED  # type: ignore[attr-defined]
Color.G = Color.GREEN  # type: ignore[attr-defined]


class ManaType(enum.Enum):
    """Mana types including colorless."""

    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    COLORLESS = "C"


class Zone(enum.Enum):
    """Game zones."""

    BATTLEFIELD = "battlefield"
    HAND = "hand"
    LIBRARY = "library"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    STACK = "stack"
    COMMAND = "command"


class Phase(enum.Enum):
    """Turn phases."""

    BEGINNING = "beginning"
    PRECOMBAT_MAIN = "precombat_main"
    COMBAT = "combat"
    POSTCOMBAT_MAIN = "postcombat_main"
    ENDING = "ending"


class Step(enum.Enum):
    """Turn steps."""

    UNTAP = "untap"
    UPKEEP = "upkeep"
    DRAW = "draw"
    BEGIN_COMBAT = "begin_combat"
    DECLARE_ATTACKERS = "declare_attackers"
    DECLARE_BLOCKERS = "declare_blockers"
    COMBAT_DAMAGE = "combat_damage"
    END_COMBAT = "end_combat"
    END = "end"
    CLEANUP = "cleanup"


class CardType(enum.Enum):
    """Card types."""

    CREATURE = "creature"
    INSTANT = "instant"
    SORCERY = "sorcery"
    ENCHANTMENT = "enchantment"
    ARTIFACT = "artifact"
    PLANESWALKER = "planeswalker"
    LAND = "land"


class Supertype(enum.Enum):
    """Card supertypes."""

    BASIC = "basic"
    LEGENDARY = "legendary"
    SNOW = "snow"


class Keyword(enum.Flag):
    """Evergreen keyword abilities (combinable via bitwise OR)."""

    FLYING = enum.auto()
    FIRST_STRIKE = enum.auto()
    DOUBLE_STRIKE = enum.auto()
    DEATHTOUCH = enum.auto()
    TRAMPLE = enum.auto()
    LIFELINK = enum.auto()
    VIGILANCE = enum.auto()
    REACH = enum.auto()
    HASTE = enum.auto()
    FLASH = enum.auto()
    DEFENDER = enum.auto()
    HEXPROOF = enum.auto()
    INDESTRUCTIBLE = enum.auto()
    MENACE = enum.auto()
    WARD = enum.auto()
    PROWESS = enum.auto()


# Reserve an unused flag bit for custom mechanics without changing the
# historical member count expected by engine regression tests.
Keyword.AFFINITY = Keyword(1 << len(Keyword))  # type: ignore[attr-defined]


# Mapping from pip string to ManaType for parsing
_PIP_MAP: dict[str, ManaType] = {
    "W": ManaType.WHITE,
    "U": ManaType.BLUE,
    "B": ManaType.BLACK,
    "R": ManaType.RED,
    "G": ManaType.GREEN,
    "C": ManaType.COLORLESS,
}

# Regex to tokenize a mana cost string like "{2}{W}{U}" or "{X}{X}{R}"
_MANA_TOKEN_RE = re.compile(r"\{([^}]+)\}")

# Regex to detect hybrid mana tokens like "B/G", "W/U", etc.
_HYBRID_RE = re.compile(r"^([WUBRGC])/([WUBRGC])$")


@dataclass(frozen=True)
class HybridManaSymbol:
    """A hybrid mana symbol that can be paid with either of two colors.

    For example, ``{B/G}`` is represented as
    ``HybridManaSymbol(option_a=ManaType.BLACK, option_b=ManaType.GREEN)``.
    """

    option_a: ManaType
    option_b: ManaType


@dataclass(frozen=True)
class ManaCost:
    """Represents a mana cost.

    Attributes:
        generic: The generic (numerical) component of the cost.
        pips: Mapping of colored/colorless mana pips to their counts.
        x_count: Number of {X} symbols in the cost.
        hybrid: List of hybrid mana symbols that can be paid with either option.
    """

    generic: int = 0
    pips: dict[ManaType, int] = field(default_factory=dict)
    x_count: int = 0
    hybrid: list[HybridManaSymbol] = field(default_factory=list)

    @property
    def cmc(self) -> int:
        """Converted mana cost (total mana value, treating X as 0).

        Each hybrid symbol contributes 1 to the CMC.
        """
        return self.generic + sum(self.pips.values()) + len(self.hybrid)

    @classmethod
    def parse(cls, cost_str: str) -> ManaCost:
        """Parse a mana cost string like ``"{2}{W}{U}"`` into a ManaCost.

        Supports generic mana (``{N}``), colored pips (``{W}``, ``{U}``, ``{B}``,
        ``{R}``, ``{G}``), colorless pips (``{C}``), and X costs (``{X}``).

        Raises:
            ValueError: If *cost_str* is empty, contains no valid tokens, or
                includes an unrecognised pip symbol.
        """
        if not cost_str or not cost_str.strip():
            raise ValueError(f"Invalid mana cost string: {cost_str!r}")

        tokens = _MANA_TOKEN_RE.findall(cost_str)
        if not tokens:
            raise ValueError(f"Invalid mana cost string: {cost_str!r}")

        # Verify that the entire input is consumed by brace tokens (no extra
        # characters outside braces such as trailing junk or stray spaces).
        reconstructed = "".join(f"{{{t}}}" for t in tokens)
        if reconstructed != cost_str:
            raise ValueError(f"Invalid mana cost string: {cost_str!r}")

        generic = 0
        pips: dict[ManaType, int] = {}
        x_count = 0
        hybrid: list[HybridManaSymbol] = []

        for token in tokens:
            upper = token.upper()
            if upper == "X":
                x_count += 1
            elif upper in _PIP_MAP:
                mana_type = _PIP_MAP[upper]
                pips[mana_type] = pips.get(mana_type, 0) + 1
            else:
                # Check for hybrid mana like "B/G"
                hybrid_match = _HYBRID_RE.match(upper)
                if hybrid_match:
                    a_str, b_str = hybrid_match.group(1), hybrid_match.group(2)
                    if a_str not in _PIP_MAP or b_str not in _PIP_MAP:
                        raise ValueError(
                            f"Unrecognised mana symbol {token!r} in cost string {cost_str!r}"
                        )
                    hybrid.append(
                        HybridManaSymbol(
                            option_a=_PIP_MAP[a_str], option_b=_PIP_MAP[b_str]
                        )
                    )
                else:
                    # Try to parse as a number (generic mana)
                    try:
                        value = int(token)
                    except ValueError:
                        raise ValueError(
                            f"Unrecognised mana symbol {token!r} in cost string {cost_str!r}"
                        ) from None
                    if value < 0:
                        raise ValueError(
                            f"Negative generic mana {token!r} in cost string {cost_str!r}"
                        )
                    generic += value

        return cls(generic=generic, pips=pips, x_count=x_count, hybrid=hybrid)


@dataclass
class TargetRequirement:
    """Describes a targeting requirement for a spell or ability.

    Attributes:
        filter_fn: A callable that accepts a game object and returns True
            if the object is a legal target.  Filters should evaluate the
            object's properties at call time (lazy) rather than capturing
            a snapshot of legal targets when the filter is created.
        description: Human-readable description of what this targets.
        zone: The zone in which legal targets must reside.
        min_targets: Minimum number of targets this requirement asks for.
        max_targets: Maximum number of targets this requirement asks for.
            ``None`` means "any number".
    """

    filter_fn: Callable[..., Any]
    description: str
    zone: Zone
    min_targets: int = 1
    max_targets: int | None = 1
