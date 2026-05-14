"""Simple creature implementations — vanilla and French vanilla from Foundations (FDN).

Vanilla creatures have no abilities (just power/toughness and a mana cost).
French vanilla creatures have only keyword abilities (no rules text beyond
the keywords).

All 15 creatures are actual cards from the MTG Foundations (FDN) set with
correct printed stats sourced from Scryfall.

Uses :func:`make_vanilla` as a generic factory to dynamically create
:class:`~engine.card.Creature` subclasses for pure-stat creatures.

Use :func:`register_simple_creatures` to register all creatures with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_vanilla(
    name: str,
    cost_str: str,
    power: int,
    toughness: int,
    keywords: Keyword | None = None,
    creature_types: set[str] | None = None,
) -> type[Creature]:
    """Create a :class:`~engine.card.Creature` subclass dynamically.

    The returned class, when instantiated, produces a creature with the
    specified stats, mana cost, keywords, and creature subtypes.  The
    constructor accepts the standard ``name``/``owner``/``controller``
    keyword arguments (matching :meth:`CardRegistry.create_instance`'s
    call convention).

    Args:
        name: Card name (used as the default ``name`` for instances and
            as the generated class name).
        cost_str: Mana cost string, e.g. ``"{1}{G}"``.
        power: Base power.
        toughness: Base toughness.
        keywords: Combined :class:`~engine.types.Keyword` flags, or
            ``None`` for vanilla creatures.
        creature_types: Set of creature-type subtype strings (e.g.
            ``{"Bear"}``).  ``None`` means no subtypes.

    Returns:
        A new ``Creature`` subclass.
    """
    # Capture parameters in the closure.
    _cost = ManaCost.parse(cost_str)
    _keywords = keywords if keywords is not None else Keyword(0)
    _subtypes = creature_types if creature_types is not None else set()
    _power = power
    _toughness = toughness
    _default_name = name

    class _VanillaCreature(Creature):
        __doc__ = f"{name} — {cost_str} {power}/{toughness}"

        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault("name", _default_name)
            kwargs.setdefault("mana_cost", _cost)
            kwargs.setdefault("keywords", _keywords)
            kwargs.setdefault("base_power", _power)
            kwargs.setdefault("base_toughness", _toughness)
            if _subtypes:
                kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | _subtypes
            super().__init__(**kwargs)

    # Give the class a readable name for debugging/repr.
    _VanillaCreature.__name__ = name.replace(" ", "").replace(",", "").replace("'", "")
    _VanillaCreature.__qualname__ = _VanillaCreature.__name__

    return _VanillaCreature


# ---------------------------------------------------------------------------
# Creature definitions — all from MTG Foundations (FDN) set
# ---------------------------------------------------------------------------

# --- Vanilla creatures (no abilities) ---

AegisTurtle = make_vanilla(
    "Aegis Turtle", "{U}", 0, 5,
    creature_types={"Turtle"},
)

SavannahLions = make_vanilla(
    "Savannah Lions", "{W}", 2, 1,
    creature_types={"Cat"},
)

BearCub = make_vanilla(
    "Bear Cub", "{1}{G}", 2, 2,
    creature_types={"Bear"},
)

SwabGoblin = make_vanilla(
    "Swab Goblin", "{1}{R}", 2, 2,
    creature_types={"Goblin", "Pirate"},
)

HighbornVampire = make_vanilla(
    "Highborn Vampire", "{3}{B}", 4, 3,
    creature_types={"Vampire", "Warrior"},
)

# --- French vanilla creatures (keywords only) ---

HealersHawk = make_vanilla(
    "Healer's Hawk", "{W}", 1, 1,
    keywords=Keyword.FLYING | Keyword.LIFELINK,
    creature_types={"Bird"},
)

BishopsSoldier = make_vanilla(
    "Bishop's Soldier", "{1}{W}", 2, 2,
    keywords=Keyword.LIFELINK,
    creature_types={"Vampire", "Soldier"},
)

LeoninSkyhunter = make_vanilla(
    "Leonin Skyhunter", "{W}{W}", 2, 2,
    keywords=Keyword.FLYING,
    creature_types={"Cat", "Knight"},
)

ThornwealdArcher = make_vanilla(
    "Thornweald Archer", "{1}{G}", 2, 1,
    keywords=Keyword.REACH | Keyword.DEATHTOUCH,
    creature_types={"Elf", "Archer"},
)

RagingRedcap = make_vanilla(
    "Raging Redcap", "{2}{R}", 1, 2,
    keywords=Keyword.DOUBLE_STRIKE,
    creature_types={"Goblin", "Knight"},
)

BrazenScourge = make_vanilla(
    "Brazen Scourge", "{1}{R}{R}", 3, 3,
    keywords=Keyword.HASTE,
    creature_types={"Gremlin"},
)

VampireNighthawk = make_vanilla(
    "Vampire Nighthawk", "{1}{B}{B}", 2, 3,
    keywords=Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK,
    creature_types={"Vampire", "Shaman"},
)

MagnigothSentry = make_vanilla(
    "Magnigoth Sentry", "{3}{G}", 4, 4,
    keywords=Keyword.REACH,
    creature_types={"Treefolk"},
)

SerraAngel = make_vanilla(
    "Serra Angel", "{3}{W}{W}", 4, 4,
    keywords=Keyword.FLYING | Keyword.VIGILANCE,
    creature_types={"Angel"},
)

TajuruPathwarden = make_vanilla(
    "Tajuru Pathwarden", "{4}{G}", 5, 4,
    keywords=Keyword.VIGILANCE | Keyword.TRAMPLE,
    creature_types={"Elf", "Warrior", "Ally"},
)


# ---------------------------------------------------------------------------
# All creatures list for registration — Scryfall-verified metadata
# ---------------------------------------------------------------------------

_ALL_SIMPLE_CREATURES: list[
    tuple[str, type[Creature], str, str, str, list[str], list[str], str, str, str]
] = [
    # (name, impl_class, mana_cost_str, power, toughness, colors,
    #  keyword_strings, rarity, type_line, collector_number)
    #
    # --- Vanilla ---
    ("Aegis Turtle", AegisTurtle, "{U}", "0", "5",
     ["U"], [], "common",
     "Creature — Turtle", "150"),
    ("Savannah Lions", SavannahLions, "{W}", "2", "1",
     ["W"], [], "uncommon",
     "Creature — Cat", "146"),
    ("Bear Cub", BearCub, "{1}{G}", "2", "2",
     ["G"], [], "common",
     "Creature — Bear", "552"),
    ("Swab Goblin", SwabGoblin, "{1}{R}", "2", "2",
     ["R"], [], "common",
     "Creature — Goblin Pirate", "548"),
    ("Highborn Vampire", HighbornVampire, "{3}{B}", "4", "3",
     ["B"], [], "common",
     "Creature — Vampire Warrior", "522"),
    #
    # --- French Vanilla ---
    ("Healer's Hawk", HealersHawk, "{W}", "1", "1",
     ["W"], ["Flying", "Lifelink"], "common",
     "Creature — Bird", "734"),
    ("Bishop's Soldier", BishopsSoldier, "{1}{W}", "2", "2",
     ["W"], ["Lifelink"], "common",
     "Creature — Vampire Soldier", "491"),
    ("Leonin Skyhunter", LeoninSkyhunter, "{W}{W}", "2", "2",
     ["W"], ["Flying"], "uncommon",
     "Creature — Cat Knight", "498"),
    ("Thornweald Archer", ThornwealdArcher, "{1}{G}", "2", "1",
     ["G"], ["Reach", "Deathtouch"], "common",
     "Creature — Elf Archer", "559"),
    ("Raging Redcap", RagingRedcap, "{2}{R}", "1", "2",
     ["R"], ["Double strike"], "common",
     "Creature — Goblin Knight", "543"),
    ("Brazen Scourge", BrazenScourge, "{1}{R}{R}", "3", "3",
     ["R"], ["Haste"], "uncommon",
     "Creature — Gremlin", "191"),
    ("Vampire Nighthawk", VampireNighthawk, "{1}{B}{B}", "2", "3",
     ["B"], ["Flying", "Deathtouch", "Lifelink"], "uncommon",
     "Creature — Vampire Shaman", "757"),
    ("Magnigoth Sentry", MagnigothSentry, "{3}{G}", "4", "4",
     ["G"], ["Reach"], "common",
     "Creature — Treefolk", "556"),
    ("Serra Angel", SerraAngel, "{3}{W}{W}", "4", "4",
     ["W"], ["Flying", "Vigilance"], "uncommon",
     "Creature — Angel", "740"),
    ("Tajuru Pathwarden", TajuruPathwarden, "{4}{G}", "5", "4",
     ["G"], ["Vigilance", "Trample"], "common",
     "Creature — Elf Warrior Ally", "558"),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_simple_creatures(registry: CardRegistry) -> None:
    """Register all simple creatures with *registry*.

    Each creature is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    power/toughness, colors, and keywords.  All metadata matches the
    actual FDN printing as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, power, toughness,
        colors, kw_strings, rarity, type_line, collector_number,
    ) in _ALL_SIMPLE_CREATURES:
        # Build oracle text: keywords joined by newlines (empty for vanilla).
        oracle_text = "\n".join(kw_strings) if kw_strings else ""

        metadata = CardMetadata(
            name=card_name,
            mana_cost_str=cost_str,
            type_line=type_line,
            oracle_text=oracle_text,
            power=power,
            toughness=toughness,
            colors=colors,
            keywords=kw_strings,
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(card_name, impl_class, metadata)
