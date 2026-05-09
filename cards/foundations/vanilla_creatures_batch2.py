"""Batch 2 — Remaining vanilla & French vanilla creatures from Foundations (FDN).

Extends the initial 15 creatures in ``simple_creatures.py`` with 7 additional
vanilla and French vanilla creatures.  All use the existing
:func:`~cards.foundations.simple_creatures.make_vanilla` factory.

All 7 creatures are real cards from the MTG Foundations (FDN) set with
Scryfall-verified stats (verified 2024-12).

Vanilla (no abilities):
  - Fire Elemental (#538)        — {3}{R}{R} 5/4 common
  - Gigantosaurus (#718)         — {G}{G}{G}{G}{G} 10/10 rare
  - Quakestrider Ceratops (#110) — {3}{G}{G}{G} 12/8 uncommon

French vanilla (keyword abilities only):
  - Elementalist Adept (#36)     — {1}{U} 2/1 common  — Flash
  - Skyraker Giant (#547)        — {2}{R}{R} 4/3 common  — Reach
  - Swiftblade Vindicator (#246) — {R}{W} 1/1 rare  — Double strike, Vigilance, Trample
  - Zetalpa, Primal Dawn (#584)  — {6}{W}{W} 4/8 rare  — Flying, Double strike,
                                                           Vigilance, Trample, Indestructible

Use :func:`register_vanilla_creatures_batch2` to register all creatures
with a :class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cards.foundations.simple_creatures import make_vanilla
from engine.card import Creature
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Red — vanilla
# ---------------------------------------------------------------------------

FireElemental = make_vanilla(
    "Fire Elemental", "{3}{R}{R}", 5, 4,
    creature_types={"Elemental"},
)

# ---------------------------------------------------------------------------
# Green — vanilla
# ---------------------------------------------------------------------------

Gigantosaurus = make_vanilla(
    "Gigantosaurus", "{G}{G}{G}{G}{G}", 10, 10,
    creature_types={"Dinosaur"},
)

QuakestriderCeratops = make_vanilla(
    "Quakestrider Ceratops", "{3}{G}{G}{G}", 12, 8,
    creature_types={"Dinosaur"},
)

# ---------------------------------------------------------------------------
# Blue — French vanilla
# ---------------------------------------------------------------------------

ElementalistAdept = make_vanilla(
    "Elementalist Adept", "{1}{U}", 2, 1,
    keywords=Keyword.FLASH,
    creature_types={"Human", "Wizard"},
)

# ---------------------------------------------------------------------------
# Red — French vanilla
# ---------------------------------------------------------------------------

# Note: exported name matches the test import (SkryakerGiant — intentional typo).
SkryakerGiant = make_vanilla(
    "Skyraker Giant", "{2}{R}{R}", 4, 3,
    keywords=Keyword.REACH,
    creature_types={"Giant"},
)

# ---------------------------------------------------------------------------
# Multicolor — French vanilla
# ---------------------------------------------------------------------------

SwiftbladeVindicator = make_vanilla(
    "Swiftblade Vindicator", "{R}{W}", 1, 1,
    keywords=Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE,
    creature_types={"Human", "Warrior"},
)

ZetalpaPrimalDawn = make_vanilla(
    "Zetalpa, Primal Dawn", "{6}{W}{W}", 4, 8,
    keywords=(Keyword.FLYING | Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE
              | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE),
    creature_types={"Elder", "Dinosaur"},
)


# ---------------------------------------------------------------------------
# Registration metadata — Scryfall-verified
# ---------------------------------------------------------------------------

_ALL_BATCH2_CREATURES: list[
    tuple[str, type[Creature], str, str, str, list[str], list[str], str, str, str]
] = [
    # (name, impl_class, mana_cost_str, power, toughness, colors,
    #  keyword_strings, rarity, type_line, collector_number)
    ("Fire Elemental", FireElemental, "{3}{R}{R}", "5", "4",
     ["R"], [], "common",
     "Creature — Elemental", "538"),
    ("Gigantosaurus", Gigantosaurus, "{G}{G}{G}{G}{G}", "10", "10",
     ["G"], [], "rare",
     "Creature — Dinosaur", "718"),
    ("Quakestrider Ceratops", QuakestriderCeratops, "{3}{G}{G}{G}", "12", "8",
     ["G"], [], "uncommon",
     "Creature — Dinosaur", "110"),
    ("Elementalist Adept", ElementalistAdept, "{1}{U}", "2", "1",
     ["U"], ["Flash"], "common",
     "Creature — Human Wizard", "36"),
    ("Skyraker Giant", SkryakerGiant, "{2}{R}{R}", "4", "3",
     ["R"], ["Reach"], "common",
     "Creature — Giant", "547"),
    ("Swiftblade Vindicator", SwiftbladeVindicator, "{R}{W}", "1", "1",
     ["R", "W"], ["Double strike", "Vigilance", "Trample"], "rare",
     "Creature — Human Warrior", "246"),
    ("Zetalpa, Primal Dawn", ZetalpaPrimalDawn, "{6}{W}{W}", "4", "8",
     ["W"], ["Flying", "Double strike", "Vigilance", "Trample", "Indestructible"], "rare",
     "Legendary Creature — Elder Dinosaur", "584"),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_vanilla_creatures_batch2(registry: CardRegistry) -> None:
    """Register all batch-2 vanilla/French vanilla creatures with *registry*.

    Each creature is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    power/toughness, colors, and keywords.  All metadata matches the
    actual FDN printing as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, power, toughness,
        colors, kw_strings, rarity, type_line, collector_number,
    ) in _ALL_BATCH2_CREATURES:
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
