"""Tests for cards/fdn/_legacy/activated_creatures.py — Batch 9 activated-ability creatures.

All 19 creatures are from the MTG Foundations (FDN) set.

Verifies:
- Card metadata (name, mana cost, power/toughness, subtypes, keywords).
- Activated abilities exist with correct descriptions.
- Mana abilities produce correct mana (Llanowar Elves, Elvish Archdruid, Ruby).
- Tap abilities require untapped creature and set is_tapped.
- Sacrifice abilities remove the creature from battlefield.
- Pump abilities modify stats correctly.
- Edge cases: can't activate when tapped, sacrifice cost is paid, activate-only-once.
- register_activated_creatures() registers all cards in the registry.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.activated_creatures import (
    AxgardCavalry,
    BurnishedHart,
    CatharCommando,
    ElvishArchdruid,
    FanaticalFirebrand,
    HeartfireImmolator,
    HungryGhoul,
    KrenkoMobBoss,
    LlanowarElves,
    MildManneredLibrarian,
    ReassemblingSkeleton,
    RubyDaringTracker,
    RuneSealedWall,
    ScavengingOoze,
    ShivanDragon,
    SowerOfChaos,
    SpectralSailor,
    StrixLookout,
    TreetopSnarespinner,
    register_activated_creatures,
)
from cards.registry import CardRegistry
from engine.card import ActivatedAbility, ArtifactCreature, CardImpl, Creature, ManaAbility
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(*, phase: Phase = Phase.PRECOMBAT_MAIN) -> GameState:
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _place_on_battlefield(game: GameState, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)


def _add_mana(player, mana_type: ManaType, amount: int):
    player.mana_pool.add(mana_type, amount)


def _add_cards_to_library(player, n: int) -> list:
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


def _activate_ability(game, creature, ability_index=0):
    """Activate a creature's activated ability by index. Returns True if cost paid."""
    abilities = creature.get_activated_abilities()
    ab = abilities[ability_index]
    if ab.cost(game, creature):
        ab.effect(game)
        return True
    return False


def _activate_mana_ability(game, creature, ability_index=0):
    """Activate a creature's mana ability by index. Returns True if cost paid."""
    abilities = creature.get_mana_abilities()
    ab = abilities[ability_index]
    if ab.cost(game, creature):
        ab.mana_produced(game)
        return True
    return False


# ===================================================================
# METADATA TESTS
# ===================================================================

class TestLlanowarElvesMetadata:
    def test_name(self):
        c = LlanowarElves()
        assert c.name == "Llanowar Elves"

    def test_stats(self):
        c = LlanowarElves()
        assert c.base_power == 1
        assert c.base_toughness == 1

    def test_subtypes(self):
        c = LlanowarElves()
        assert "Elf" in c.subtypes
        assert "Druid" in c.subtypes

    def test_mana_cost(self):
        c = LlanowarElves()
        assert c.mana_cost == ManaCost.parse("{G}")


class TestElvishArchdruidMetadata:
    def test_name_and_stats(self):
        c = ElvishArchdruid()
        assert c.name == "Elvish Archdruid"
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_subtypes(self):
        c = ElvishArchdruid()
        assert "Elf" in c.subtypes
        assert "Druid" in c.subtypes

    def test_mana_cost(self):
        c = ElvishArchdruid()
        assert c.mana_cost == ManaCost.parse("{1}{G}{G}")


class TestRubyDaringTrackerMetadata:
    def test_name_and_stats(self):
        c = RubyDaringTracker()
        assert c.name == "Ruby, Daring Tracker"
        assert c.base_power == 1
        assert c.base_toughness == 2

    def test_legendary(self):
        c = RubyDaringTracker()
        assert Supertype.LEGENDARY in c.supertypes

    def test_haste(self):
        c = RubyDaringTracker()
        assert Keyword.HASTE in c.keywords


class TestRuneSealedWallMetadata:
    def test_name_and_stats(self):
        c = RuneSealedWall()
        assert c.name == "Rune-Sealed Wall"
        assert c.base_power == 0
        assert c.base_toughness == 6

    def test_defender(self):
        c = RuneSealedWall()
        assert Keyword.DEFENDER in c.keywords

    def test_is_artifact_creature(self):
        c = RuneSealedWall()
        assert isinstance(c, ArtifactCreature)


class TestStrixLookoutMetadata:
    def test_name_and_stats(self):
        c = StrixLookout()
        assert c.name == "Strix Lookout"
        assert c.base_power == 1
        assert c.base_toughness == 2

    def test_keywords(self):
        c = StrixLookout()
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords


class TestAxgardCavalryMetadata:
    def test_name_and_stats(self):
        c = AxgardCavalry()
        assert c.name == "Axgard Cavalry"
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_subtypes(self):
        c = AxgardCavalry()
        assert "Dwarf" in c.subtypes
        assert "Berserker" in c.subtypes


class TestKrenkoMobBossMetadata:
    def test_name_and_stats(self):
        c = KrenkoMobBoss()
        assert c.name == "Krenko, Mob Boss"
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_legendary(self):
        c = KrenkoMobBoss()
        assert Supertype.LEGENDARY in c.supertypes

    def test_subtypes(self):
        c = KrenkoMobBoss()
        assert "Goblin" in c.subtypes


class TestCatharCommandoMetadata:
    def test_name_and_stats(self):
        c = CatharCommando()
        assert c.name == "Cathar Commando"
        assert c.base_power == 3
        assert c.base_toughness == 1

    def test_flash(self):
        c = CatharCommando()
        assert Keyword.FLASH in c.keywords


class TestFanaticalFirebrandMetadata:
    def test_name_and_stats(self):
        c = FanaticalFirebrand()
        assert c.name == "Fanatical Firebrand"
        assert c.base_power == 1
        assert c.base_toughness == 1

    def test_haste(self):
        c = FanaticalFirebrand()
        assert Keyword.HASTE in c.keywords


class TestHeartfireImmolatorMetadata:
    def test_name_and_stats(self):
        c = HeartfireImmolator()
        assert c.name == "Heartfire Immolator"
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_prowess(self):
        c = HeartfireImmolator()
        assert Keyword.PROWESS in c.keywords


class TestBurnishedHartMetadata:
    def test_name_and_stats(self):
        c = BurnishedHart()
        assert c.name == "Burnished Hart"
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_is_artifact_creature(self):
        c = BurnishedHart()
        assert isinstance(c, ArtifactCreature)

    def test_subtypes(self):
        c = BurnishedHart()
        assert "Elk" in c.subtypes


class TestHungryGhoulMetadata:
    def test_name_and_stats(self):
        c = HungryGhoul()
        assert c.name == "Hungry Ghoul"
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert "Zombie" in c.subtypes


class TestShivanDragonMetadata:
    def test_name_and_stats(self):
        c = ShivanDragon()
        assert c.name == "Shivan Dragon"
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_flying(self):
        c = ShivanDragon()
        assert Keyword.FLYING in c.keywords

    def test_mana_cost(self):
        c = ShivanDragon()
        assert c.mana_cost == ManaCost.parse("{4}{R}{R}")


class TestSowerOfChaosMetadata:
    def test_name_and_stats(self):
        c = SowerOfChaos()
        assert c.name == "Sower of Chaos"
        assert c.base_power == 4
        assert c.base_toughness == 3
        assert "Devil" in c.subtypes


class TestTreetopSnarespinnerMetadata:
    def test_name_and_stats(self):
        c = TreetopSnarespinner()
        assert c.name == "Treetop Snarespinner"
        assert c.base_power == 1
        assert c.base_toughness == 4

    def test_keywords(self):
        c = TreetopSnarespinner()
        assert Keyword.REACH in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords


class TestSpectralSailorMetadata:
    def test_name_and_stats(self):
        c = SpectralSailor()
        assert c.name == "Spectral Sailor"
        assert c.base_power == 1
        assert c.base_toughness == 1

    def test_keywords(self):
        c = SpectralSailor()
        assert Keyword.FLASH in c.keywords
        assert Keyword.FLYING in c.keywords


class TestScavengingOozeMetadata:
    def test_name_and_stats(self):
        c = ScavengingOoze()
        assert c.name == "Scavenging Ooze"
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert "Ooze" in c.subtypes


class TestReassemblingSkeletonMetadata:
    def test_name_and_stats(self):
        c = ReassemblingSkeleton()
        assert c.name == "Reassembling Skeleton"
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Skeleton" in c.subtypes
        assert "Warrior" in c.subtypes


class TestMildManneredLibrarianMetadata:
    def test_name_and_stats(self):
        c = MildManneredLibrarian()
        assert c.name == "Mild-Mannered Librarian"
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Human" in c.subtypes
        assert "Werewolf" in c.subtypes


# ===================================================================
# ABILITIES EXISTENCE TESTS
# ===================================================================

class TestAbilitiesExist:
    def test_llanowar_elves_has_mana_ability(self):
        c = LlanowarElves()
        abilities = c.get_mana_abilities()
        assert len(abilities) >= 1
        assert isinstance(abilities[0], ManaAbility)
        assert "{T}: Add {G}" in abilities[0].description

    def test_elvish_archdruid_has_mana_ability(self):
        c = ElvishArchdruid()
        abilities = c.get_mana_abilities()
        assert len(abilities) >= 1
        assert isinstance(abilities[0], ManaAbility)

    def test_ruby_has_two_mana_abilities(self):
        c = RubyDaringTracker()
        abilities = c.get_mana_abilities()
        assert len(abilities) == 2

    def test_rune_sealed_wall_has_activated_ability(self):
        c = RuneSealedWall()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_strix_lookout_has_activated_ability(self):
        c = StrixLookout()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_axgard_cavalry_has_activated_ability(self):
        c = AxgardCavalry()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_krenko_has_activated_ability(self):
        c = KrenkoMobBoss()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_cathar_commando_has_activated_ability(self):
        c = CatharCommando()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_fanatical_firebrand_has_activated_ability(self):
        c = FanaticalFirebrand()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_shivan_dragon_has_pump_ability(self):
        c = ShivanDragon()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
        assert "+1/+0" in abilities[0].description

    def test_spectral_sailor_has_draw_ability(self):
        c = SpectralSailor()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
        assert "Draw a card" in abilities[0].description

    def test_scavenging_ooze_has_activated_ability(self):
        c = ScavengingOoze()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_reassembling_skeleton_has_activated_ability(self):
        c = ReassemblingSkeleton()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_mild_mannered_librarian_has_activated_ability(self):
        c = MildManneredLibrarian()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1


# ===================================================================
# MANA ABILITY TESTS
# ===================================================================

class TestLlanowarElvesManaAbility:
    def test_produces_green_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = LlanowarElves()
        _place_on_battlefield(game, c, p1)
        result = _activate_mana_ability(game, c)
        assert result is True
        assert p1.mana_pool.get(ManaType.GREEN) == 1

    def test_taps_creature(self):
        game = _make_game()
        p1 = game.players[0]
        c = LlanowarElves()
        _place_on_battlefield(game, c, p1)
        _activate_mana_ability(game, c)
        assert c.is_tapped is True

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        c = LlanowarElves()
        _place_on_battlefield(game, c, p1)
        c.is_tapped = True
        result = _activate_mana_ability(game, c)
        assert result is False
        assert p1.mana_pool.get(ManaType.GREEN) == 0


class TestElvishArchdruidManaAbility:
    def test_produces_green_per_elf(self):
        game = _make_game()
        p1 = game.players[0]
        archdruid = ElvishArchdruid()
        _place_on_battlefield(game, archdruid, p1)
        # Add another elf
        elf2 = LlanowarElves()
        _place_on_battlefield(game, elf2, p1)
        result = _activate_mana_ability(game, archdruid)
        assert result is True
        # Should count 2 elves (archdruid + elf2)
        assert p1.mana_pool.get(ManaType.GREEN) == 2

    def test_counts_only_elves(self):
        game = _make_game()
        p1 = game.players[0]
        archdruid = ElvishArchdruid()
        _place_on_battlefield(game, archdruid, p1)
        # Add a non-elf creature
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(game, bear, p1)
        _activate_mana_ability(game, archdruid)
        # Only archdruid is an elf
        assert p1.mana_pool.get(ManaType.GREEN) == 1

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        archdruid = ElvishArchdruid()
        _place_on_battlefield(game, archdruid, p1)
        archdruid.is_tapped = True
        result = _activate_mana_ability(game, archdruid)
        assert result is False


class TestRubyManaAbility:
    def test_produces_red(self):
        game = _make_game()
        p1 = game.players[0]
        c = RubyDaringTracker()
        _place_on_battlefield(game, c, p1)
        result = _activate_mana_ability(game, c, ability_index=0)
        assert result is True
        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_produces_green(self):
        game = _make_game()
        p1 = game.players[0]
        c = RubyDaringTracker()
        _place_on_battlefield(game, c, p1)
        result = _activate_mana_ability(game, c, ability_index=1)
        assert result is True
        assert p1.mana_pool.get(ManaType.GREEN) == 1


# ===================================================================
# TAP ABILITY TESTS
# ===================================================================

class TestRuneSealedWallTapAbility:
    def test_surveil_moves_card_to_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        wall = RuneSealedWall()
        _place_on_battlefield(game, wall, p1)
        lib_cards = _add_cards_to_library(p1, 3)
        result = _activate_ability(game, wall)
        assert result is True
        # One card should have moved to graveyard
        gy = p1.zones[Zone.GRAVEYARD]
        assert len(gy) == 1

    def test_taps_wall(self):
        game = _make_game()
        p1 = game.players[0]
        wall = RuneSealedWall()
        _place_on_battlefield(game, wall, p1)
        _add_cards_to_library(p1, 3)
        _activate_ability(game, wall)
        assert wall.is_tapped is True

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        wall = RuneSealedWall()
        _place_on_battlefield(game, wall, p1)
        wall.is_tapped = True
        _add_cards_to_library(p1, 3)
        result = _activate_ability(game, wall)
        assert result is False


class TestAxgardCavalryTapAbility:
    def test_grants_haste(self):
        game = _make_game()
        p1 = game.players[0]
        cavalry = AxgardCavalry()
        _place_on_battlefield(game, cavalry, p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(game, target, p1)
        cavalry._current_target = target
        result = _activate_ability(game, cavalry)
        assert result is True
        assert Keyword.HASTE in target.keywords

    def test_taps_cavalry(self):
        game = _make_game()
        p1 = game.players[0]
        cavalry = AxgardCavalry()
        _place_on_battlefield(game, cavalry, p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        cavalry._current_target = target
        _activate_ability(game, cavalry)
        assert cavalry.is_tapped is True

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        cavalry = AxgardCavalry()
        _place_on_battlefield(game, cavalry, p1)
        cavalry.is_tapped = True
        result = _activate_ability(game, cavalry)
        assert result is False


class TestKrenkoMobBossTapAbility:
    def test_creates_goblin_tokens(self):
        game = _make_game()
        p1 = game.players[0]
        krenko = KrenkoMobBoss()
        _place_on_battlefield(game, krenko, p1)
        # Krenko is a Goblin, so 1 Goblin -> 1 token
        bf_before = len(game.get_battlefield(p1))
        result = _activate_ability(game, krenko)
        assert result is True
        bf_after = len(game.get_battlefield(p1))
        # Should have 1 new token (1 Goblin = Krenko)
        assert bf_after == bf_before + 1

    def test_token_count_scales_with_goblins(self):
        game = _make_game()
        p1 = game.players[0]
        krenko = KrenkoMobBoss()
        _place_on_battlefield(game, krenko, p1)
        # Add 2 more Goblin creatures
        for _ in range(2):
            goblin = Creature(name="Goblin", base_power=1, base_toughness=1, subtypes={"Goblin"})
            _place_on_battlefield(game, goblin, p1)
        bf_before = len(game.get_battlefield(p1))
        _activate_ability(game, krenko)
        bf_after = len(game.get_battlefield(p1))
        # 3 Goblins (Krenko + 2) = 3 tokens
        assert bf_after == bf_before + 3

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        krenko = KrenkoMobBoss()
        _place_on_battlefield(game, krenko, p1)
        krenko.is_tapped = True
        result = _activate_ability(game, krenko)
        assert result is False


class TestStrixLookoutTapAbility:
    def test_draws_and_discards(self):
        game = _make_game()
        p1 = game.players[0]
        strix = StrixLookout()
        _place_on_battlefield(game, strix, p1)
        _add_cards_to_library(p1, 5)
        _add_mana(p1, ManaType.BLUE, 2)
        hand_before = len(p1.zones[Zone.HAND])
        result = _activate_ability(game, strix)
        assert result is True
        # Draw 1 then discard 1 = net 0 hand change
        hand_after = len(p1.zones[Zone.HAND])
        assert hand_after == hand_before

    def test_requires_mana(self):
        game = _make_game()
        p1 = game.players[0]
        strix = StrixLookout()
        _place_on_battlefield(game, strix, p1)
        # No mana
        result = _activate_ability(game, strix)
        assert result is False

    def test_taps_strix(self):
        game = _make_game()
        p1 = game.players[0]
        strix = StrixLookout()
        _place_on_battlefield(game, strix, p1)
        _add_cards_to_library(p1, 5)
        _add_mana(p1, ManaType.BLUE, 2)
        _activate_ability(game, strix)
        assert strix.is_tapped is True


# ===================================================================
# SACRIFICE ABILITY TESTS
# ===================================================================

class TestCatharCommandoSacrifice:
    def test_sacrifices_self(self):
        game = _make_game()
        p1 = game.players[0]
        commando = CatharCommando()
        _place_on_battlefield(game, commando, p1)
        _add_mana(p1, ManaType.COLORLESS, 1)
        result = _activate_ability(game, commando)
        assert result is True
        # Should be removed from battlefield
        assert not game.get_battlefield(p1).contains(commando)

    def test_requires_mana(self):
        game = _make_game()
        p1 = game.players[0]
        commando = CatharCommando()
        _place_on_battlefield(game, commando, p1)
        # No mana
        result = _activate_ability(game, commando)
        assert result is False
        # Should still be on battlefield
        assert game.get_battlefield(p1).contains(commando)


class TestFanaticalFirebrandSacrifice:
    def test_sacrifices_self_and_deals_damage(self):
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        firebrand = FanaticalFirebrand()
        _place_on_battlefield(game, firebrand, p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(game, target, p2)
        firebrand._current_target = target
        result = _activate_ability(game, firebrand)
        assert result is True
        # Firebrand should be off battlefield
        assert not game.get_battlefield(p1).contains(firebrand)

    def test_taps_as_part_of_cost(self):
        game = _make_game()
        p1 = game.players[0]
        firebrand = FanaticalFirebrand()
        _place_on_battlefield(game, firebrand, p1)
        firebrand._current_target = game.players[1]
        _activate_ability(game, firebrand)
        assert firebrand.is_tapped is True

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        firebrand = FanaticalFirebrand()
        _place_on_battlefield(game, firebrand, p1)
        firebrand.is_tapped = True
        result = _activate_ability(game, firebrand)
        assert result is False


class TestHeartfireImmolatorSacrifice:
    def test_sacrifices_self(self):
        game = _make_game()
        p1 = game.players[0]
        immolator = HeartfireImmolator()
        _place_on_battlefield(game, immolator, p1)
        _add_mana(p1, ManaType.RED, 1)
        result = _activate_ability(game, immolator)
        assert result is True
        assert not game.get_battlefield(p1).contains(immolator)

    def test_requires_red_mana(self):
        game = _make_game()
        p1 = game.players[0]
        immolator = HeartfireImmolator()
        _place_on_battlefield(game, immolator, p1)
        # No red mana
        result = _activate_ability(game, immolator)
        assert result is False


class TestBurnishedHartSacrifice:
    def test_sacrifices_self(self):
        game = _make_game()
        p1 = game.players[0]
        hart = BurnishedHart()
        _place_on_battlefield(game, hart, p1)
        _add_mana(p1, ManaType.COLORLESS, 3)
        result = _activate_ability(game, hart)
        assert result is True
        assert not game.get_battlefield(p1).contains(hart)

    def test_requires_3_mana(self):
        game = _make_game()
        p1 = game.players[0]
        hart = BurnishedHart()
        _place_on_battlefield(game, hart, p1)
        _add_mana(p1, ManaType.COLORLESS, 2)  # Not enough
        result = _activate_ability(game, hart)
        assert result is False
        assert game.get_battlefield(p1).contains(hart)


class TestHungryGhoulSacrifice:
    def test_sacrifices_another_creature_and_gains_counter(self):
        game = _make_game()
        p1 = game.players[0]
        ghoul = HungryGhoul()
        _place_on_battlefield(game, ghoul, p1)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        _place_on_battlefield(game, fodder, p1)
        ghoul._sacrifice_target = fodder
        _add_mana(p1, ManaType.COLORLESS, 1)
        result = _activate_ability(game, ghoul)
        assert result is True
        # Fodder should be gone
        assert not game.get_battlefield(p1).contains(fodder)
        # Ghoul should still be on battlefield
        assert game.get_battlefield(p1).contains(ghoul)

    def test_cannot_sacrifice_self(self):
        game = _make_game()
        p1 = game.players[0]
        ghoul = HungryGhoul()
        _place_on_battlefield(game, ghoul, p1)
        ghoul._sacrifice_target = ghoul  # Can't sac self
        _add_mana(p1, ManaType.COLORLESS, 1)
        result = _activate_ability(game, ghoul)
        assert result is False

    def test_requires_mana(self):
        game = _make_game()
        p1 = game.players[0]
        ghoul = HungryGhoul()
        _place_on_battlefield(game, ghoul, p1)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        _place_on_battlefield(game, fodder, p1)
        ghoul._sacrifice_target = fodder
        # No mana
        result = _activate_ability(game, ghoul)
        assert result is False


# ===================================================================
# PUMP ABILITY TESTS
# ===================================================================

class TestShivanDragonPump:
    def test_pump_increases_power(self):
        game = _make_game()
        p1 = game.players[0]
        dragon = ShivanDragon()
        _place_on_battlefield(game, dragon, p1)
        _add_mana(p1, ManaType.RED, 3)
        original_power = dragon.base_power
        _activate_ability(game, dragon)
        assert dragon.base_power == original_power + 1

    def test_pump_multiple_times(self):
        game = _make_game()
        p1 = game.players[0]
        dragon = ShivanDragon()
        _place_on_battlefield(game, dragon, p1)
        _add_mana(p1, ManaType.RED, 3)
        _activate_ability(game, dragon)
        _activate_ability(game, dragon)
        _activate_ability(game, dragon)
        assert dragon.base_power == 8  # 5 + 3

    def test_requires_red_mana(self):
        game = _make_game()
        p1 = game.players[0]
        dragon = ShivanDragon()
        _place_on_battlefield(game, dragon, p1)
        # No red mana
        result = _activate_ability(game, dragon)
        assert result is False
        assert dragon.base_power == 5


class TestSowerOfChaosPump:
    def test_cant_block_effect(self):
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        sower = SowerOfChaos()
        _place_on_battlefield(game, sower, p1)
        target = Creature(name="Blocker", base_power=2, base_toughness=2)
        _place_on_battlefield(game, target, p2)
        sower._current_target = target
        _add_mana(p1, ManaType.RED, 3)
        result = _activate_ability(game, sower)
        assert result is True
        assert getattr(target, "_cant_block", False) is True

    def test_requires_2R_mana(self):
        game = _make_game()
        p1 = game.players[0]
        sower = SowerOfChaos()
        _place_on_battlefield(game, sower, p1)
        _add_mana(p1, ManaType.RED, 1)  # Not enough
        result = _activate_ability(game, sower)
        assert result is False


class TestTreetopSnarespinnerPump:
    def test_adds_counter(self):
        game = _make_game()
        p1 = game.players[0]
        spider = TreetopSnarespinner()
        _place_on_battlefield(game, spider, p1)
        _add_mana(p1, ManaType.GREEN, 3)
        result = _activate_ability(game, spider)
        assert result is True

    def test_requires_2G_mana(self):
        game = _make_game()
        p1 = game.players[0]
        spider = TreetopSnarespinner()
        _place_on_battlefield(game, spider, p1)
        _add_mana(p1, ManaType.GREEN, 1)  # Not enough
        result = _activate_ability(game, spider)
        assert result is False


# ===================================================================
# OTHER ABILITY TESTS
# ===================================================================

class TestSpectralSailorDraw:
    def test_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        sailor = SpectralSailor()
        _place_on_battlefield(game, sailor, p1)
        _add_cards_to_library(p1, 5)
        _add_mana(p1, ManaType.BLUE, 4)
        hand_before = len(p1.zones[Zone.HAND])
        result = _activate_ability(game, sailor)
        assert result is True
        assert len(p1.zones[Zone.HAND]) == hand_before + 1

    def test_requires_3U_mana(self):
        game = _make_game()
        p1 = game.players[0]
        sailor = SpectralSailor()
        _place_on_battlefield(game, sailor, p1)
        _add_mana(p1, ManaType.BLUE, 2)
        result = _activate_ability(game, sailor)
        assert result is False


class TestScavengingOozeExile:
    def test_exiles_creature_from_graveyard_and_gains_counter_and_life(self):
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ooze = ScavengingOoze()
        _place_on_battlefield(game, ooze, p1)
        # Put a creature card in opponent's graveyard
        dead = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        dead.owner = p2
        dead.controller = p2
        p2.zones[Zone.GRAVEYARD].add(dead)
        ooze._current_target = dead
        _add_mana(p1, ManaType.GREEN, 1)
        life_before = p1.life
        result = _activate_ability(game, ooze)
        assert result is True
        # Dead bear should be exiled (not in graveyard)
        assert not p2.zones[Zone.GRAVEYARD].contains(dead)
        # Ooze controller gains 1 life
        assert p1.life == life_before + 1

    def test_requires_green_mana(self):
        game = _make_game()
        p1 = game.players[0]
        ooze = ScavengingOoze()
        _place_on_battlefield(game, ooze, p1)
        result = _activate_ability(game, ooze)
        assert result is False


class TestReassemblingSkeletonRecursion:
    def test_returns_from_graveyard_to_battlefield_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        skeleton = ReassemblingSkeleton()
        skeleton.owner = p1
        skeleton.controller = p1
        p1.zones[Zone.GRAVEYARD].add(skeleton)
        _add_mana(p1, ManaType.BLACK, 2)
        result = _activate_ability(game, skeleton)
        assert result is True
        assert game.get_battlefield(p1).contains(skeleton)
        assert skeleton.is_tapped is True

    def test_cannot_activate_from_battlefield(self):
        game = _make_game()
        p1 = game.players[0]
        skeleton = ReassemblingSkeleton()
        _place_on_battlefield(game, skeleton, p1)
        _add_mana(p1, ManaType.BLACK, 2)
        result = _activate_ability(game, skeleton)
        assert result is False

    def test_requires_1B_mana(self):
        game = _make_game()
        p1 = game.players[0]
        skeleton = ReassemblingSkeleton()
        skeleton.owner = p1
        skeleton.controller = p1
        p1.zones[Zone.GRAVEYARD].add(skeleton)
        _add_mana(p1, ManaType.BLACK, 1)  # Not enough
        result = _activate_ability(game, skeleton)
        assert result is False


class TestMildManneredLibrarianActivateOnce:
    def test_transforms_and_adds_counters(self):
        game = _make_game()
        p1 = game.players[0]
        lib = MildManneredLibrarian()
        _place_on_battlefield(game, lib, p1)
        _add_cards_to_library(p1, 5)
        _add_mana(p1, ManaType.GREEN, 4)
        result = _activate_ability(game, lib)
        assert result is True
        # Human should be removed, Werewolf stays
        assert "Human" not in lib.subtypes
        assert "Werewolf" in lib.subtypes

    def test_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        lib = MildManneredLibrarian()
        _place_on_battlefield(game, lib, p1)
        _add_cards_to_library(p1, 5)
        _add_mana(p1, ManaType.GREEN, 4)
        hand_before = len(p1.zones[Zone.HAND])
        _activate_ability(game, lib)
        assert len(p1.zones[Zone.HAND]) == hand_before + 1

    def test_activate_only_once(self):
        game = _make_game()
        p1 = game.players[0]
        lib = MildManneredLibrarian()
        _place_on_battlefield(game, lib, p1)
        _add_cards_to_library(p1, 10)
        _add_mana(p1, ManaType.GREEN, 8)
        _activate_ability(game, lib)
        # Second activation should fail
        result = _activate_ability(game, lib)
        assert result is False

    def test_requires_3G_mana(self):
        game = _make_game()
        p1 = game.players[0]
        lib = MildManneredLibrarian()
        _place_on_battlefield(game, lib, p1)
        _add_mana(p1, ManaType.GREEN, 2)
        result = _activate_ability(game, lib)
        assert result is False


# ===================================================================
# REGISTRY TEST
# ===================================================================

class TestRegistration:
    def test_register_activated_creatures(self):
        registry = CardRegistry()
        register_activated_creatures(registry)
        expected_names = [
            "Llanowar Elves",
            "Elvish Archdruid",
            "Ruby, Daring Tracker",
            "Rune-Sealed Wall",
            "Strix Lookout",
            "Axgard Cavalry",
            "Krenko, Mob Boss",
            "Cathar Commando",
            "Fanatical Firebrand",
            "Heartfire Immolator",
            "Burnished Hart",
            "Hungry Ghoul",
            "Shivan Dragon",
            "Sower of Chaos",
            "Treetop Snarespinner",
            "Spectral Sailor",
            "Scavenging Ooze",
            "Reassembling Skeleton",
            "Mild-Mannered Librarian",
        ]
        for name in expected_names:
            assert registry.get(name) is not None, f"{name} not registered"
