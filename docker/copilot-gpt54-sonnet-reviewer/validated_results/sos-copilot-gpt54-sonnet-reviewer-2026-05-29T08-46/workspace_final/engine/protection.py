"""Protection from qualities — keyword ability implementation.

Implements the 'protection from [quality]' keyword per MTG rules.
Protection prevents (DEBT mnemonic):
  - **D**amage from sources with that quality
  - **E**nchanting/equipping by permanents with that quality
  - **B**locking by creatures with that quality
  - **T**argeting by spells/abilities from sources with that quality

Phase 1 supports color-based protection.  The framework is extensible to
card-type, subtype, and arbitrary predicate-based protection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from engine.types import Color, ManaType

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

# Map from ManaType to Color for deriving a card's colours from its mana cost.
_MANA_TO_COLOR: dict[ManaType, Color] = {
    ManaType.WHITE: Color.WHITE,
    ManaType.BLUE: Color.BLUE,
    ManaType.BLACK: Color.BLACK,
    ManaType.RED: Color.RED,
    ManaType.GREEN: Color.GREEN,
}


def get_colors(obj: Any) -> set[Color]:
    """Return the set of colours of *obj*.

    Colour is determined by:
    1. An explicit ``colors`` attribute (set or list of :class:`Color`).
    2. The coloured pips in the object's ``mana_cost``.
    3. An explicit ``color`` attribute (single :class:`Color`).

    Colourless objects return an empty set.
    """
    # Explicit colors attribute (takes precedence)
    if hasattr(obj, "colors") and obj.colors is not None:
        explicit_colors = set(obj.colors)
        if explicit_colors:
            return explicit_colors

    # Derive from mana cost pips
    mana_cost = getattr(obj, "mana_cost", None)
    if mana_cost is not None:
        pips = getattr(mana_cost, "pips", None)
        if pips:
            result: set[Color] = set()
            for mt in pips:
                if mt in _MANA_TO_COLOR:
                    result.add(_MANA_TO_COLOR[mt])
            return result

    # Single color attribute fallback
    if hasattr(obj, "color") and obj.color is not None:
        return {obj.color}

    return set()


# ---------------------------------------------------------------------------
# ProtectionAbility
# ---------------------------------------------------------------------------

@dataclass
class ProtectionAbility:
    """Represents a 'protection from [quality]' ability.

    The *quality* is typically a :class:`Color`, but the framework supports
    arbitrary predicates via *predicate*.

    Usage::

        # Colour-based protection
        pro_red = ProtectionAbility(quality=Color.RED)

        # Custom predicate (e.g. protection from artifacts)
        pro_artifacts = ProtectionAbility(
            quality="artifacts",
            predicate=lambda src: CardType.ARTIFACT in getattr(src, "card_types", set()),
        )

    Attributes:
        quality: A human-readable label for the quality (often a
            :class:`Color` enum member).
        predicate: An optional callable ``(source) -> bool`` that returns
            ``True`` if *source* has the protected-from quality.  When
            ``None``, the quality must be a :class:`Color` and the default
            colour-matching predicate is used.
    """

    quality: Any  # typically Color, but may be str or CardType
    predicate: Callable[[Any], bool] | None = None

    def matches(self, source: Any) -> bool:
        """Return ``True`` if *source* has the quality this protects from."""
        if self.predicate is not None:
            return self.predicate(source)

        # Default: colour-based matching
        if isinstance(self.quality, Color):
            return self.quality in get_colors(source)

        return False


# ---------------------------------------------------------------------------
# Query helpers — work with any object that has a ``protections`` list
# ---------------------------------------------------------------------------

def get_protections(obj: Any) -> list[ProtectionAbility]:
    """Return the list of :class:`ProtectionAbility` on *obj*, or ``[]``."""
    return getattr(obj, "protections", [])


def has_protection_from(permanent: Any, source: Any) -> bool:
    """Return ``True`` if *permanent* has protection from *source*.

    Iterates over all :class:`ProtectionAbility` instances on *permanent*
    and returns ``True`` if any matches *source*.
    """
    for prot in get_protections(permanent):
        if prot.matches(source):
            return True
    return False


def _is_illegal_target_due_to_protection(target: Any, source: Any) -> bool:
    """Return ``True`` if *target* cannot be targeted by *source* due to protection."""
    return has_protection_from(target, source)


def _is_illegal_block_due_to_protection(attacker: Any, blocker: Any) -> bool:
    """Return ``True`` if *attacker* has protection from *blocker*.

    Protection prevents blocking *by* creatures with that quality —
    i.e. the attacker is the one with protection, the blocker is checked.
    """
    return has_protection_from(attacker, blocker)


def _should_prevent_damage(target: Any, source: Any) -> bool:
    """Return ``True`` if damage from *source* to *target* should be prevented."""
    return has_protection_from(target, source)


def _aura_illegal_due_to_protection(aura: Any) -> bool:
    """Return ``True`` if *aura* is illegally attached due to protection.

    An aura is illegal if the enchanted permanent has protection from the
    aura (checked via the aura's colours / quality).
    """
    attached = getattr(aura, "attached_to", None)
    if attached is None:
        return False
    return has_protection_from(attached, aura)
