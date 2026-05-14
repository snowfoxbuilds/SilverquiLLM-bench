"""Tests for cards/fdn/_legacy/vanilla_creatures_batch2.py — Batch 2 vanilla & French vanilla creatures.

All 7 creatures are REAL cards from the MTG Foundations (FDN) set with
Scryfall-verified stats (verified against Scryfall API 2024-12).

These are the remaining vanilla/French vanilla creatures in FDN that were
NOT already implemented in simple_creatures.py (batch 1).

Vanilla (no abilities):
  - Fire Elemental (#538)       — {3}{R}{R} 5/4 common
  - Gigantosaurus (#718)        — {G}{G}{G}{G}{G} 10/10 rare
  - Quakestrider Ceratops (#110) — {3}{G}{G}{G} 12/8 uncommon

French vanilla (keyword abilities only):
  - Elementalist Adept (#36)    — {1}{U} 2/1 common  — Flash, Prowess
  - Skyraker Giant (#547)       — {2}{R}{R} 4/3 common  — Reach
  - Swiftblade Vindicator (#246) — {R}{W} 1/1 rare  — Double strike, Vigilance, Trample
  - Zetalpa, Primal Dawn (#584) — {6}{W}{W} 4/8 rare  — Flying, Double strike,
                                                          Vigilance, Trample, Indestructible

Verifies:
- Each creature has the correct name, mana_cost, power, toughness, and keywords.
- Vanilla creatures have no keyword abilities set.
- French vanilla creatures have exactly the right keyword abilities, no extras.
- register_vanilla_creatures_batch2() registers all 7 creatures in the registry.
- Registry metadata accuracy (collector_number, rarity, set_code, type_line).
- Integration: cast creature, verify it enters battlefield with correct stats/keywords.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.vanilla_creatures_batch2 import (
    ElementalistAdept,
    FireElemental,
    Gigantosaurus,
    QuakestriderCeratops,
    SkryakerGiant,
    SwiftbladeVindicator,
    ZetalpaPrimalDawn,
    register_vanilla_creatures_batch2,
)
from cards.registry import CardRegistry
from engine.card import Creature
from engine.player import DeterministicPlayer
from engine.game_state import GameState
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone

from tests.test_utils import create_game, set_board_state, cast_spell


# ---------------------------------------------------------------------------
# Stat verification — parameterized tests for all 7 creatures
# ---------------------------------------------------------------------------

_CREATURE_STATS = [
    # (class, expected_name, cost_str, power, toughness, expected_keywords)
    # --- Vanilla ---
    (FireElemental, "Fire Elemental", "{3}{R}{R}", 5, 4, Keyword(0)),
    (Gigantosaurus, "Gigantosaurus", "{G}{G}{G}{G}{G}", 10, 10, Keyword(0)),
    (QuakestriderCeratops, "Quakestrider Ceratops", "{3}{G}{G}{G}", 12, 8, Keyword(0)),
    # --- French vanilla ---
    (ElementalistAdept, "Elementalist Adept", "{1}{U}", 2, 1,
     Keyword.FLASH),
    (SkryakerGiant, "Skyraker Giant", "{2}{R}{R}", 4, 3, Keyword.REACH),
    (SwiftbladeVindicator, "Swiftblade Vindicator", "{R}{W}", 1, 1,
     Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE),
    (ZetalpaPrimalDawn, "Zetalpa, Primal Dawn", "{6}{W}{W}", 4, 8,
     Keyword.FLYING | Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE
     | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE),
]


class TestCreatureAttributes:
    """Verify each creature's name, mana cost, power, toughness, and keywords."""

    @pytest.mark.parametrize(
        "cls, expected_name, cost_str, power, toughness, expected_keywords",
        _CREATURE_STATS,
        ids=[s[1] for s in _CREATURE_STATS],
    )
    def test_creature_attributes(
        self, cls, expected_name, cost_str, power, toughness, expected_keywords,
    ) -> None:
        creature = cls()
        assert creature.name == expected_name
        assert creature.mana_cost == ManaCost.parse(cost_str)
        assert creature.power == power
        assert creature.toughness == toughness
        assert creature.keywords == expected_keywords

    @pytest.mark.parametrize("cls,name", [
        (FireElemental, "Fire Elemental"),
        (Gigantosaurus, "Gigantosaurus"),
        (QuakestriderCeratops, "Quakestrider Ceratops"),
    ], ids=lambda x: x if isinstance(x, str) else x.__name__)
    def test_vanilla_has_no_keywords(self, cls, name) -> None:
        """Vanilla creatures must have Keyword(0) — no abilities."""
        creature = cls()
        assert creature.keywords == Keyword(0), (
            f"{name} should have no keywords but has {creature.keywords!r}"
        )

    @pytest.mark.parametrize(
        "cls, expected_keywords, name",
        [
            (ElementalistAdept, Keyword.FLASH, "Elementalist Adept"),
            (SkryakerGiant, Keyword.REACH, "Skyraker Giant"),
            (SwiftbladeVindicator,
             Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE,
             "Swiftblade Vindicator"),
            (ZetalpaPrimalDawn,
             Keyword.FLYING | Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE
             | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE,
             "Zetalpa, Primal Dawn"),
        ],
        ids=lambda x: x if isinstance(x, str) else "",
    )
    def test_french_vanilla_exact_keywords(self, cls, expected_keywords, name) -> None:
        """French vanilla creatures must have exactly the expected keywords."""
        creature = cls()
        assert creature.keywords == expected_keywords, (
            f"{name}: expected {expected_keywords!r}, got {creature.keywords!r}"
        )

    def test_all_are_creature_subclasses(self) -> None:
        """Every batch-2 creature class must be a Creature subclass."""
        for cls, name, *_ in _CREATURE_STATS:
            assert issubclass(cls, Creature), f"{name} is not a Creature subclass"

    def test_all_have_creature_card_type(self) -> None:
        """Every batch-2 creature instance must have CardType.CREATURE."""
        for cls, name, *_ in _CREATURE_STATS:
            creature = cls()
            assert CardType.CREATURE in creature.card_types, (
                f"{name} missing CardType.CREATURE"
            )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Verify register_vanilla_creatures_batch2() populates registry correctly."""

    @pytest.fixture()
    def registry(self) -> CardRegistry:
        reg = CardRegistry()
        register_vanilla_creatures_batch2(reg)
        return reg

    def test_registers_all_7_creatures(self, registry: CardRegistry) -> None:
        """All 7 creatures should be registered."""
        names = [s[1] for s in _CREATURE_STATS]
        for name in names:
            assert name in registry, f"{name!r} not found in registry"

    def test_registered_count(self, registry: CardRegistry) -> None:
        """Registry should contain exactly 7 entries."""
        assert len(registry) == 7

    def test_create_instance_produces_creature(self, registry: CardRegistry) -> None:
        """create_instance for any batch-2 creature should return a Creature."""
        for _, name, *_ in _CREATURE_STATS:
            instance = registry.create_instance(name)
            assert isinstance(instance, Creature), (
                f"create_instance({name!r}) did not return a Creature"
            )

    _COLLECTOR_NUMBERS = [
        ("Fire Elemental", "538"),
        ("Gigantosaurus", "718"),
        ("Quakestrider Ceratops", "110"),
        ("Elementalist Adept", "36"),
        ("Skyraker Giant", "547"),
        ("Swiftblade Vindicator", "246"),
        ("Zetalpa, Primal Dawn", "584"),
    ]

    @pytest.mark.parametrize("name, collector_number", _COLLECTOR_NUMBERS,
                             ids=[c[0] for c in _COLLECTOR_NUMBERS])
    def test_collector_number(self, registry: CardRegistry, name, collector_number) -> None:
        """Each creature's collector number must match Scryfall data."""
        _cls, meta = registry.get(name)
        assert meta.collector_number == collector_number

    def test_set_code_is_fdn(self, registry: CardRegistry) -> None:
        """All batch-2 creatures should have set_code 'fdn'."""
        for _, name, *_ in _CREATURE_STATS:
            _cls, meta = registry.get(name)
            assert meta.set_code == "fdn", f"{name} set_code is {meta.set_code!r}"

    _RARITY_CHECKS = [
        ("Fire Elemental", "common"),
        ("Gigantosaurus", "rare"),
        ("Quakestrider Ceratops", "uncommon"),
        ("Elementalist Adept", "common"),
        ("Skyraker Giant", "common"),
        ("Swiftblade Vindicator", "rare"),
        ("Zetalpa, Primal Dawn", "rare"),
    ]

    @pytest.mark.parametrize("name, rarity", _RARITY_CHECKS,
                             ids=[r[0] for r in _RARITY_CHECKS])
    def test_rarity(self, registry: CardRegistry, name, rarity) -> None:
        """Rarity values must match Scryfall data."""
        _cls, meta = registry.get(name)
        assert meta.rarity == rarity

    def test_metadata_keywords_zetalpa(self, registry: CardRegistry) -> None:
        """Zetalpa metadata should list all five keyword strings."""
        _cls, meta = registry.get("Zetalpa, Primal Dawn")
        kw_lower = [k.lower() for k in meta.keywords]
        assert "flying" in kw_lower
        assert "trample" in kw_lower
        assert "indestructible" in kw_lower
        assert "vigilance" in kw_lower
        assert "double strike" in kw_lower

    def test_metadata_keywords_skyraker(self, registry: CardRegistry) -> None:
        """Skyraker Giant metadata should list Reach."""
        _cls, meta = registry.get("Skyraker Giant")
        kw_lower = [k.lower() for k in meta.keywords]
        assert "reach" in kw_lower

    def test_metadata_keywords_vanilla_empty(self, registry: CardRegistry) -> None:
        """Vanilla creature metadata should have no keywords."""
        _cls, meta = registry.get("Fire Elemental")
        assert meta.keywords == [] or meta.keywords == ()

    def test_metadata_type_line_zetalpa_legendary(self, registry: CardRegistry) -> None:
        """Zetalpa should have 'Legendary' in its type line."""
        _cls, meta = registry.get("Zetalpa, Primal Dawn")
        assert "Legendary" in meta.type_line

    def test_metadata_type_line_fire_elemental(self, registry: CardRegistry) -> None:
        """Fire Elemental type line should include Elemental."""
        _cls, meta = registry.get("Fire Elemental")
        assert "Elemental" in meta.type_line

    def test_metadata_type_line_gigantosaurus(self, registry: CardRegistry) -> None:
        """Gigantosaurus type line should include Dinosaur."""
        _cls, meta = registry.get("Gigantosaurus")
        assert "Dinosaur" in meta.type_line


# ---------------------------------------------------------------------------
# Integration tests — cast creature, verify on battlefield
# ---------------------------------------------------------------------------

class TestCastingIntegration:
    """Cast a representative subset of creatures and verify battlefield state."""

    def _make_game_with_creature_in_hand(self, creature_cls):
        """Create a game with a creature in player 0's hand and enough mana."""
        creature = creature_cls()
        game = create_game()
        set_board_state(game, 0, hand=[creature])
        # Give player enough mana of every type to cast anything
        mana = {
            ManaType.WHITE: 10,
            ManaType.BLUE: 10,
            ManaType.BLACK: 10,
            ManaType.RED: 10,
            ManaType.GREEN: 10,
            ManaType.COLORLESS: 10,
        }
        set_board_state(game, 0, mana=mana)
        return game, creature

    def test_cast_fire_elemental_enters_battlefield(self) -> None:
        """Fire Elemental (vanilla red 5/4) enters battlefield after casting."""
        game, _ = self._make_game_with_creature_in_hand(FireElemental)
        cast_spell(game, 0, "Fire Elemental")
        bf = game.get_battlefield(game.players[0])
        creatures = [c for c in bf.get_all() if isinstance(c, Creature)]
        assert len(creatures) == 1
        assert creatures[0].name == "Fire Elemental"
        assert creatures[0].power == 5
        assert creatures[0].toughness == 4

    def test_cast_gigantosaurus_stats(self) -> None:
        """Gigantosaurus (vanilla green 10/10) enters with correct stats."""
        game, _ = self._make_game_with_creature_in_hand(Gigantosaurus)
        cast_spell(game, 0, "Gigantosaurus")
        bf = game.get_battlefield(game.players[0])
        creatures = [c for c in bf.get_all() if isinstance(c, Creature)]
        assert len(creatures) == 1
        assert creatures[0].power == 10
        assert creatures[0].toughness == 10

    def test_cast_skyraker_giant_has_reach(self) -> None:
        """Skyraker Giant enters battlefield with reach keyword."""
        game, _ = self._make_game_with_creature_in_hand(SkryakerGiant)
        cast_spell(game, 0, "Skyraker Giant")
        bf = game.get_battlefield(game.players[0])
        creatures = [c for c in bf.get_all() if isinstance(c, Creature)]
        assert len(creatures) == 1
        assert creatures[0].name == "Skyraker Giant"
        assert Keyword.REACH in creatures[0].keywords

    def test_cast_zetalpa_has_all_keywords(self) -> None:
        """Zetalpa enters battlefield with all five keywords."""
        game, _ = self._make_game_with_creature_in_hand(ZetalpaPrimalDawn)
        cast_spell(game, 0, "Zetalpa, Primal Dawn")
        bf = game.get_battlefield(game.players[0])
        creatures = [c for c in bf.get_all() if isinstance(c, Creature)]
        assert len(creatures) == 1
        assert creatures[0].power == 4
        assert creatures[0].toughness == 8
        assert Keyword.FLYING in creatures[0].keywords
        assert Keyword.DOUBLE_STRIKE in creatures[0].keywords
        assert Keyword.VIGILANCE in creatures[0].keywords
        assert Keyword.TRAMPLE in creatures[0].keywords
        assert Keyword.INDESTRUCTIBLE in creatures[0].keywords

    def test_cast_swiftblade_vindicator_keywords(self) -> None:
        """Swiftblade Vindicator enters with double strike, vigilance, trample."""
        game, _ = self._make_game_with_creature_in_hand(SwiftbladeVindicator)
        cast_spell(game, 0, "Swiftblade Vindicator")
        bf = game.get_battlefield(game.players[0])
        creatures = [c for c in bf.get_all() if isinstance(c, Creature)]
        assert len(creatures) == 1
        assert creatures[0].power == 1
        assert creatures[0].toughness == 1
        assert Keyword.DOUBLE_STRIKE in creatures[0].keywords
        assert Keyword.VIGILANCE in creatures[0].keywords
        assert Keyword.TRAMPLE in creatures[0].keywords
