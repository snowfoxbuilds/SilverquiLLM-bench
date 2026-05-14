"""Tests for cards/fdn/_legacy/simple_creatures.py — Vanilla and French vanilla creatures.

All 15 creatures are from the MTG Foundations (FDN) set with Scryfall-verified stats.

Verifies:
- Each creature has the correct name, mana_cost, power, toughness, and card types.
- Vanilla creatures have no keyword abilities set.
- French vanilla creatures have exactly the right keyword abilities, no extras.
- The make_vanilla factory produces valid Creature subclasses.
- register_simple_creatures() registers all 15 creatures in the registry.
- Registry metadata accuracy (oracle_text, rarity, set_code, type_line).
- Integration: keyword mechanics work in combat (flying, first strike, vigilance,
  trample, lifelink, deathtouch, haste, reach, menace, defender, double strike).
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.simple_creatures import (
    AegisTurtle,
    BearCub,
    BishopsSoldier,
    BrazenScourge,
    HealersHawk,
    HighbornVampire,
    LeoninSkyhunter,
    MagnigothSentry,
    RagingRedcap,
    SavannahLions,
    SerraAngel,
    SwabGoblin,
    TajuruPathwarden,
    ThornwealdArcher,
    VampireNighthawk,
    make_vanilla,
    register_simple_creatures,
)
from cards.registry import CardRegistry
from engine.card import Creature
from engine.combat import (
    combat_damage_step,
    declare_attackers_step,
    declare_blockers_step,
)
from engine.player import DeterministicPlayer
from engine.game_state import GameState
from engine.types import CardType, Keyword, ManaCost, Phase, Step, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    return game


def _setup_combat(
    attacker_classes: list[type[Creature]],
    blocker_classes: list[type[Creature]],
) -> tuple[GameState, list[Creature], list[Creature]]:
    """Set up a combat scenario with specified attacker and blocker creature types.

    Returns (game, attacker_instances, blocker_instances) with creatures on
    the battlefield, summoning sickness cleared, and the phase set to combat.
    """
    p1 = DeterministicPlayer("Attacker", [])
    p2 = DeterministicPlayer("Defender", [])
    game = GameState([p1, p2])
    game.phase = Phase.COMBAT
    game.step = Step.DECLARE_ATTACKERS
    game.active_player_index = 0

    attackers = []
    for cls in attacker_classes:
        c = cls(owner=p1, controller=p1)
        c.summoning_sick = False
        p1.zones[Zone.BATTLEFIELD].add(c)
        attackers.append(c)

    blockers = []
    for cls in blocker_classes:
        c = cls(owner=p2, controller=p2)
        c.summoning_sick = False
        p2.zones[Zone.BATTLEFIELD].add(c)
        blockers.append(c)

    return game, attackers, blockers


# ---------------------------------------------------------------------------
# Stat verification — parameterized tests for all 15 FDN creatures
# ---------------------------------------------------------------------------

_CREATURE_STATS = [
    # (class, expected_name, cost_str, power, toughness, expected_keywords, creature_types)
    # --- Vanilla ---
    (AegisTurtle, "Aegis Turtle", "{U}", 0, 5, Keyword(0), {"Turtle"}),
    (SavannahLions, "Savannah Lions", "{W}", 2, 1, Keyword(0), {"Cat"}),
    (BearCub, "Bear Cub", "{1}{G}", 2, 2, Keyword(0), {"Bear"}),
    (SwabGoblin, "Swab Goblin", "{1}{R}", 2, 2, Keyword(0), {"Goblin", "Pirate"}),
    (HighbornVampire, "Highborn Vampire", "{3}{B}", 4, 3, Keyword(0), {"Vampire", "Warrior"}),
    # --- French Vanilla ---
    (HealersHawk, "Healer's Hawk", "{W}", 1, 1,
     Keyword.FLYING | Keyword.LIFELINK, {"Bird"}),
    (BishopsSoldier, "Bishop's Soldier", "{1}{W}", 2, 2,
     Keyword.LIFELINK, {"Vampire", "Soldier"}),
    (LeoninSkyhunter, "Leonin Skyhunter", "{W}{W}", 2, 2,
     Keyword.FLYING, {"Cat", "Knight"}),
    (ThornwealdArcher, "Thornweald Archer", "{1}{G}", 2, 1,
     Keyword.REACH | Keyword.DEATHTOUCH, {"Elf", "Archer"}),
    (RagingRedcap, "Raging Redcap", "{2}{R}", 1, 2,
     Keyword.DOUBLE_STRIKE, {"Goblin", "Knight"}),
    (BrazenScourge, "Brazen Scourge", "{1}{R}{R}", 3, 3,
     Keyword.HASTE, {"Gremlin"}),
    (VampireNighthawk, "Vampire Nighthawk", "{1}{B}{B}", 2, 3,
     Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK, {"Vampire", "Shaman"}),
    (MagnigothSentry, "Magnigoth Sentry", "{3}{G}", 4, 4,
     Keyword.REACH, {"Treefolk"}),
    (SerraAngel, "Serra Angel", "{3}{W}{W}", 4, 4,
     Keyword.FLYING | Keyword.VIGILANCE, {"Angel"}),
    (TajuruPathwarden, "Tajuru Pathwarden", "{4}{G}", 5, 4,
     Keyword.VIGILANCE | Keyword.TRAMPLE, {"Elf", "Warrior", "Ally"}),
]


class TestCreatureStats:
    """Verify each creature has the correct name, mana cost, power, toughness,
    card types, and keyword abilities."""

    @pytest.mark.parametrize(
        "cls,expected_name,cost_str,power,toughness,expected_keywords,creature_types",
        _CREATURE_STATS,
        ids=[s[1] for s in _CREATURE_STATS],
    )
    def test_creature_attributes(
        self, cls, expected_name, cost_str, power, toughness, expected_keywords, creature_types
    ) -> None:
        """Verify name, mana_cost, power, toughness, card_types, keywords, and subtypes."""
        c = cls()
        assert c.name == expected_name
        assert c.mana_cost == ManaCost.parse(cost_str)
        assert c.power == power
        assert c.toughness == toughness
        assert CardType.CREATURE in c.card_types
        assert c.keywords == expected_keywords
        assert creature_types.issubset(c.subtypes)


class TestVanillaCreaturesHaveNoKeywords:
    """Vanilla creatures should have exactly zero keyword abilities."""

    @pytest.mark.parametrize("cls,name", [
        (AegisTurtle, "Aegis Turtle"),
        (SavannahLions, "Savannah Lions"),
        (BearCub, "Bear Cub"),
        (SwabGoblin, "Swab Goblin"),
        (HighbornVampire, "Highborn Vampire"),
    ])
    def test_no_keywords(self, cls, name) -> None:
        c = cls()
        # Keyword(0) is the "no flags" value
        assert c.keywords == Keyword(0), f"{name} should have no keyword abilities"


class TestFrenchVanillaExactKeywords:
    """French vanilla creatures should have exactly the specified keywords, no extras."""

    @pytest.mark.parametrize(
        "cls,expected_keywords,name",
        [
            (HealersHawk, Keyword.FLYING | Keyword.LIFELINK, "Healer's Hawk"),
            (BishopsSoldier, Keyword.LIFELINK, "Bishop's Soldier"),
            (LeoninSkyhunter, Keyword.FLYING, "Leonin Skyhunter"),
            (ThornwealdArcher, Keyword.REACH | Keyword.DEATHTOUCH, "Thornweald Archer"),
            (RagingRedcap, Keyword.DOUBLE_STRIKE, "Raging Redcap"),
            (BrazenScourge, Keyword.HASTE, "Brazen Scourge"),
            (VampireNighthawk, Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK,
             "Vampire Nighthawk"),
            (MagnigothSentry, Keyword.REACH, "Magnigoth Sentry"),
            (SerraAngel, Keyword.FLYING | Keyword.VIGILANCE, "Serra Angel"),
            (TajuruPathwarden, Keyword.VIGILANCE | Keyword.TRAMPLE, "Tajuru Pathwarden"),
        ],
    )
    def test_exact_keywords(self, cls, expected_keywords, name) -> None:
        c = cls()
        assert c.keywords == expected_keywords, (
            f"{name} should have exactly {expected_keywords!r}, got {c.keywords!r}"
        )


class TestMakeVanillaFactory:
    """Verify the make_vanilla factory produces valid Creature subclasses."""

    def test_factory_creates_creature_subclass(self) -> None:
        cls = make_vanilla("Test Bear", "{1}{G}", 2, 2, creature_types={"Bear"})
        instance = cls()
        assert isinstance(instance, Creature)

    def test_factory_no_keywords_default(self) -> None:
        """When keywords=None, the creature should have no keywords."""
        cls = make_vanilla("Blank", "{1}", 1, 1)
        instance = cls()
        assert instance.keywords == Keyword(0)

    def test_factory_passes_keywords(self) -> None:
        """When keywords are specified, they should be set on the instance."""
        cls = make_vanilla("Flyer", "{U}", 1, 1, keywords=Keyword.FLYING)
        instance = cls()
        assert Keyword.FLYING in instance.keywords

    def test_factory_different_calls_create_distinct_classes(self) -> None:
        cls_a = make_vanilla("A", "{1}", 1, 1)
        cls_b = make_vanilla("B", "{2}", 2, 2)
        assert cls_a is not cls_b
        assert cls_a().name == "A"
        assert cls_b().name == "B"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegisterSimpleCreatures:
    """Verify register_simple_creatures registers all 15 FDN creatures."""

    def test_registers_all_fifteen(self) -> None:
        registry = CardRegistry()
        register_simple_creatures(registry)
        assert len(registry) == 15

    def test_registered_names(self) -> None:
        registry = CardRegistry()
        register_simple_creatures(registry)
        expected_names = {
            "Aegis Turtle", "Savannah Lions", "Bear Cub", "Swab Goblin",
            "Highborn Vampire", "Healer's Hawk", "Bishop's Soldier",
            "Leonin Skyhunter", "Thornweald Archer", "Raging Redcap",
            "Brazen Scourge", "Vampire Nighthawk", "Magnigoth Sentry",
            "Serra Angel", "Tajuru Pathwarden",
        }
        assert set(registry.list_all()) == expected_names

    def test_create_instance_produces_creature(self) -> None:
        registry = CardRegistry()
        register_simple_creatures(registry)
        player = _make_player()
        for name in registry.list_all():
            instance = registry.create_instance(name, owner=player)
            assert isinstance(instance, Creature), f"{name} should be a Creature"
            assert instance.owner is player

    def test_registry_metadata_serra_angel_stats(self) -> None:
        """Serra Angel metadata should have correct P/T and keywords."""
        registry = CardRegistry()
        register_simple_creatures(registry)
        _cls, meta = registry.get("Serra Angel")
        assert meta.power == "4"
        assert meta.toughness == "4"
        assert "Flying" in meta.keywords
        assert "Vigilance" in meta.keywords

    def test_registry_metadata_vanilla_no_keywords(self) -> None:
        """Vanilla creatures should have empty keywords list in metadata."""
        registry = CardRegistry()
        register_simple_creatures(registry)
        _cls, meta = registry.get("Aegis Turtle")
        assert meta.keywords == []

    def test_registry_metadata_set_code_is_fdn(self) -> None:
        """All creatures should be registered with set_code 'fdn'."""
        registry = CardRegistry()
        register_simple_creatures(registry)
        for name in registry.list_all():
            _cls, meta = registry.get(name)
            assert meta.set_code == "fdn", f"{name} set_code should be 'fdn'"

    def test_registry_metadata_type_line_and_oracle_text(self) -> None:
        """Type line should include 'Creature' and subtypes; oracle text
        should contain keywords for French vanilla and be empty for vanilla."""
        registry = CardRegistry()
        register_simple_creatures(registry)
        # French vanilla: Vampire Nighthawk
        _cls, meta_fv = registry.get("Vampire Nighthawk")
        assert meta_fv.type_line == "Creature — Vampire Shaman"
        assert "Flying" in meta_fv.oracle_text
        assert "Deathtouch" in meta_fv.oracle_text
        assert "Lifelink" in meta_fv.oracle_text
        # Vanilla: Bear Cub
        _cls, meta_v = registry.get("Bear Cub")
        assert meta_v.oracle_text == ""

    def test_registry_metadata_rarity(self) -> None:
        """Spot-check rarity for a common and an uncommon creature."""
        registry = CardRegistry()
        register_simple_creatures(registry)
        _cls, meta_common = registry.get("Bear Cub")
        assert meta_common.rarity == "common"
        _cls, meta_uncommon = registry.get("Serra Angel")
        assert meta_uncommon.rarity == "uncommon"


# ---------------------------------------------------------------------------
# Combat keyword mechanic integration tests
# ---------------------------------------------------------------------------

class TestFlyingBlocking:
    """Flying creatures can only be blocked by creatures with flying or reach."""

    def test_ground_creature_cannot_block_flyer(self) -> None:
        """Bear Cub (ground) should not legally block Leonin Skyhunter (flying)."""
        game, [flyer], [ground] = _setup_combat(
            [LeoninSkyhunter], [BearCub],
        )

        p1 = game.players[0]
        p1._script.appendleft([flyer])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({ground: flyer})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        assert ground not in game.combat_state.blockers

    def test_reach_creature_can_block_flyer(self) -> None:
        """Magnigoth Sentry (reach) should be able to block Serra Angel (flying)."""
        game, [flyer], [reacher] = _setup_combat(
            [SerraAngel], [MagnigothSentry],
        )

        p1 = game.players[0]
        p1._script.appendleft([flyer])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({reacher: flyer})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        assert reacher in game.combat_state.blockers

    def test_flying_creature_can_block_flyer(self) -> None:
        """Healer's Hawk (flying) can block Leonin Skyhunter (flying)."""
        game, [attacker], [blocker] = _setup_combat(
            [LeoninSkyhunter], [HealersHawk],
        )

        p1 = game.players[0]
        p1._script.appendleft([attacker])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({blocker: attacker})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        assert blocker in game.combat_state.blockers


class TestVigilance:
    """Creatures with vigilance don't tap when attacking."""

    def test_vigilance_attacker_stays_untapped(self) -> None:
        """Serra Angel (flying + vigilance) should not tap when declared as attacker."""
        game, [angel], [] = _setup_combat([SerraAngel], [])

        p1 = game.players[0]
        p1._script.appendleft([angel])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        assert angel.is_attacking is True
        assert angel.is_tapped is False

    def test_non_vigilance_attacker_taps(self) -> None:
        """Bear Cub (no vigilance) should tap when attacking."""
        game, [bear], [] = _setup_combat([BearCub], [])

        p1 = game.players[0]
        p1._script.appendleft([bear])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        assert bear.is_attacking is True
        assert bear.is_tapped is True


class TestDoubleStrike:
    """Double strike creatures deal damage in both first-strike and normal steps."""

    def test_double_strike_deals_damage_in_both_substeps(self) -> None:
        """Raging Redcap (1/2 double strike) unblocked deals 1 in first-strike
        sub-step and 1 in normal sub-step = 2 total to defending player."""
        game, [redcap], [] = _setup_combat([RagingRedcap], [])

        p1 = game.players[0]
        p1._script.appendleft([redcap])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        defender_life_before = game.players[1].life
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # Double strike: 1 damage first-strike + 1 damage normal = 2 total
        assert game.players[1].life == defender_life_before - 2


class TestTrample:
    """Trample excess damage goes to the defending player."""

    def test_trample_excess_damage_to_player(self) -> None:
        """Tajuru Pathwarden (5/4 trample + vigilance) blocked by Bear Cub (2/2):
        2 damage to bear, 3 excess to defending player."""
        game, [pathwarden], [bear] = _setup_combat(
            [TajuruPathwarden], [BearCub],
        )

        p1 = game.players[0]
        p1._script.appendleft([pathwarden])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({bear: pathwarden})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        defender_life_before = game.players[1].life
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # Bear takes lethal damage (at least 2)
        assert bear.damage_marked >= 2
        # Defender takes 5 - 2 = 3 trample damage
        assert game.players[1].life == defender_life_before - 3

    def test_no_trample_no_excess_damage(self) -> None:
        """Highborn Vampire (4/3, no trample) blocked by Bear Cub (2/2):
        no excess damage to the defending player."""
        game, [vampire], [bear] = _setup_combat(
            [HighbornVampire], [BearCub],
        )

        p1 = game.players[0]
        p1._script.appendleft([vampire])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({bear: vampire})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        defender_life_before = game.players[1].life
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # No trample, so no damage to defender
        assert game.players[1].life == defender_life_before


class TestLifelink:
    """Lifelink creatures gain life for their controller equal to damage dealt."""

    def test_lifelink_unblocked_gains_life(self) -> None:
        """Healer's Hawk (1/1 flying + lifelink) attacking unblocked should
        gain 1 life for its controller and deal 1 damage to defender."""
        game, [hawk], [] = _setup_combat([HealersHawk], [])

        p1 = game.players[0]
        p1._script.appendleft([hawk])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        attacker_life_before = p1.life
        defender_life_before = game.players[1].life
        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # Controller gains 1 life from lifelink
        assert p1.life == attacker_life_before + 1
        # Defender takes 1 damage
        assert game.players[1].life == defender_life_before - 1


class TestDeathtouch:
    """Deathtouch creatures deal lethal damage regardless of toughness."""

    def test_deathtouch_marks_creature_for_sba_destruction(self) -> None:
        """Thornweald Archer (2/1 reach + deathtouch) blocking Highborn Vampire (4/3):
        the vampire should be marked with dealt_deathtouch_damage."""
        game, [vampire], [archer] = _setup_combat(
            [HighbornVampire], [ThornwealdArcher],
        )

        p1 = game.players[0]
        p1._script.appendleft([vampire])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({archer: vampire})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # Archer dealt 2 damage with deathtouch → vampire's flag should be set
        assert vampire.dealt_deathtouch_damage is True
        assert vampire.damage_marked >= 1


class TestHaste:
    """Haste creatures can attack despite summoning sickness."""

    def test_haste_creature_can_attack_with_summoning_sickness(self) -> None:
        """Brazen Scourge (3/3 haste) should be eligible to attack even with
        summoning_sick=True."""
        game = _make_game(phase=Phase.COMBAT)
        game.step = Step.DECLARE_ATTACKERS
        game.active_player_index = 0
        p1 = game.players[0]

        scourge = BrazenScourge(owner=p1, controller=p1)
        scourge.summoning_sick = True  # just created
        p1.zones[Zone.BATTLEFIELD].add(scourge)

        p1._script.appendleft([scourge])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        assert scourge.is_attacking is True

    def test_non_haste_creature_cannot_attack_with_summoning_sickness(self) -> None:
        """Bear Cub (no haste) should NOT be able to attack with summoning sickness."""
        game = _make_game(phase=Phase.COMBAT)
        game.step = Step.DECLARE_ATTACKERS
        game.active_player_index = 0
        p1 = game.players[0]

        bear = BearCub(owner=p1, controller=p1)
        bear.summoning_sick = True
        p1.zones[Zone.BATTLEFIELD].add(bear)

        p1._script.appendleft([bear])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        assert bear not in game.combat_state.attackers


class TestDefender:
    """Defender creatures cannot attack."""

    def test_defender_cannot_be_declared_as_attacker(self) -> None:
        """A creature with defender (created via make_vanilla) should not be
        eligible to attack."""
        DefenderWall = make_vanilla(
            "Test Wall", "{2}", 0, 5, keywords=Keyword.DEFENDER,
        )
        game = _make_game(phase=Phase.COMBAT)
        game.step = Step.DECLARE_ATTACKERS
        game.active_player_index = 0
        p1 = game.players[0]

        wall = DefenderWall(owner=p1, controller=p1)
        wall.summoning_sick = False
        p1.zones[Zone.BATTLEFIELD].add(wall)

        p1._script.appendleft([wall])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        assert wall not in game.combat_state.attackers


class TestMenace:
    """Menace creatures require at least 2 blockers."""

    def test_menace_with_single_blocker_is_treated_as_unblocked(self) -> None:
        """A creature with menace (created via make_vanilla) with only 1 blocker —
        the block should be rejected."""
        MenaceCreature = make_vanilla(
            "Test Menace", "{2}{B}", 3, 2, keywords=Keyword.MENACE,
        )
        game, [menace_atk], [bear] = _setup_combat(
            [MenaceCreature], [BearCub],
        )

        p1 = game.players[0]
        p1._script.appendleft([menace_atk])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({bear: menace_atk})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        blocker_list = game.combat_state.attacker_blockers.get(menace_atk, [])
        assert len(blocker_list) == 0, (
            "Menace creature should not be legally blocked by only 1 creature"
        )


class TestFirstStrike:
    """First strike creatures deal damage before normal damage."""

    def test_first_strike_blocker_kills_before_normal_damage(self) -> None:
        """A first strike blocker (1/2 via make_vanilla) blocking a 2/1 attacker:
        the first-strike blocker deals 1 damage in the first-strike step,
        killing the 2/1. The attacker never deals normal damage back."""
        FirstStrikeBlocker = make_vanilla(
            "Test FS Blocker", "{W}", 1, 2, keywords=Keyword.FIRST_STRIKE,
        )
        Attacker21 = make_vanilla("Test Attacker", "{1}{R}", 2, 1)

        game, [attacker], [blocker] = _setup_combat(
            [Attacker21], [FirstStrikeBlocker],
        )

        p1 = game.players[0]
        p1._script.appendleft([attacker])
        game.combat_state.in_combat = True
        declare_attackers_step(game)

        p2 = game.players[1]
        p2._script.appendleft({blocker: attacker})
        game.step = Step.DECLARE_BLOCKERS
        declare_blockers_step(game)

        game.step = Step.COMBAT_DAMAGE
        combat_damage_step(game)

        # First-strike blocker dealt 1 to attacker (toughness 1 → lethal)
        assert attacker.damage_marked >= 1
        # Blocker (first strike) killed attacker before normal damage,
        # so blocker takes NO damage
        assert blocker.damage_marked == 0
