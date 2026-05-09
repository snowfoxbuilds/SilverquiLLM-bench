"""Tests for cards/foundations/death_trigger_creatures.py — Batch 8 death-trigger creatures.

All 17 creatures are from the MTG Foundations (FDN) set.

Verifies:
- Card metadata (name, mana cost, power/toughness, subtypes, keywords).
- Death trigger registers correctly via register_triggers().
- Death trigger fires on CREATURE_DIES event and effect resolves:
  tokens, draw, mill/surveil, drain/damage, graveyard recursion, library search.
- Trigger does NOT fire for other creatures dying (self-death triggers).
- "Another creature dies" triggers DO fire for others but NOT self.
- Graveyard recursion returns the correct card.
- register_death_trigger_creatures() registers all cards in the registry.
"""

from __future__ import annotations

import pytest

from cards.foundations.death_trigger_creatures import (
    CrosswayTroublemakers,
    CrowOfDarkTidings,
    DriverOfTheDead,
    FiendishPanda,
    GarnaBloodfistOfKeld,
    GleamingBarrier,
    HighSocietyHunter,
    InfernalVessel,
    InfestationSage,
    KalastriaHighborn,
    MaalfeldTwins,
    MidnightReaper,
    NineLivesFamiliar,
    SolemnSimulacrum,
    SpinnerOfSouls,
    VengefulBloodwitch,
    WaryThespian,
    register_death_trigger_creatures,
)
from cards.registry import CardRegistry
from engine.card import ArtifactCreature, CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Phase, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _add_cards_to_library(player: DeterministicPlayer, n: int) -> list:
    """Add n dummy cards to a player's library and return them."""
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


def _place_on_battlefield(game: GameState, creature, player):
    """Place creature on a player's battlefield with ownership set."""
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)


def _simulate_death(game: GameState, creature, controller=None):
    """Register triggers then fire CREATURE_DIES event, then resolve stack.

    Simulates a creature dying:
    1. Register its triggers (so the death handler is listening).
    2. Fire CREATURE_DIES with the creature as the dying creature.
    3. Resolve all stack objects pushed by the trigger.
    """
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EventType.CREATURE_DIES,
        {"creature": creature, "controller": controller},
    )
    # Resolve all triggered abilities on the stack
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _simulate_another_death(game: GameState, source, dying_creature, controller=None):
    """Fire CREATURE_DIES for dying_creature, with source's triggers already registered.

    Used for testing "whenever another creature dies" triggers where
    source is already on the battlefield with triggers registered.
    """
    if controller is None:
        controller = getattr(dying_creature, "controller", game.players[0])
    game.trigger_manager.fire_event(
        game,
        EventType.CREATURE_DIES,
        {"creature": dying_creature, "controller": controller},
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ===================================================================
# TOKEN CREATION ON DEATH
# ===================================================================


class TestInfestationSage:
    """Infestation Sage — {B} 1/1 Elf Warlock — dies: create 1/1 Insect with flying."""

    def test_stats(self) -> None:
        c = InfestationSage()
        assert c.name == "Infestation Sage"
        assert c.mana_cost == ManaCost.parse("{B}")
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Elf" in c.subtypes
        assert "Warlock" in c.subtypes

    def test_death_creates_insect_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        sage = InfestationSage(owner=p1, controller=p1)
        _place_on_battlefield(game, sage, p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        _simulate_death(game, sage, p1)
        bf = game.get_battlefield(p1).get_all()
        # Token should be on battlefield (sage might still be there since we didn't move it)
        tokens = [c for c in bf if getattr(c, "name", "") == "Insect"]
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1
        assert Keyword.FLYING in tokens[0].keywords

    def test_death_does_not_fire_for_other_creature(self) -> None:
        """Self-death condition should not match when another creature dies."""
        game = _make_game()
        p1 = game.players[0]
        sage = InfestationSage(owner=p1, controller=p1)
        _place_on_battlefield(game, sage, p1)
        sage.register_triggers(game)

        other = Creature(name="Other", base_power=1, base_toughness=1, owner=p1, controller=p1)
        _simulate_another_death(game, sage, other, p1)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "name", "") == "Insect"]
        assert len(tokens) == 0


class TestGleamingBarrier:
    """Gleaming Barrier — {2} 0/4 Wall Defender — dies: create Treasure token."""

    def test_stats(self) -> None:
        c = GleamingBarrier()
        assert c.name == "Gleaming Barrier"
        assert c.mana_cost == ManaCost.parse("{2}")
        assert c.base_power == 0
        assert c.base_toughness == 4
        assert "Wall" in c.subtypes
        assert Keyword.DEFENDER in c.keywords
        assert isinstance(c, ArtifactCreature)

    def test_death_creates_treasure_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        barrier = GleamingBarrier(owner=p1, controller=p1)
        _place_on_battlefield(game, barrier, p1)
        _simulate_death(game, barrier, p1)
        bf = game.get_battlefield(p1).get_all()
        treasures = [c for c in bf if getattr(c, "name", "") == "Treasure"]
        assert len(treasures) == 1


class TestMaalfeldTwins:
    """Maalfeld Twins — {5}{B} 4/4 Zombie — dies: create two 2/2 Zombie tokens."""

    def test_stats(self) -> None:
        c = MaalfeldTwins()
        assert c.name == "Maalfeld Twins"
        assert c.mana_cost == ManaCost.parse("{5}{B}")
        assert c.base_power == 4
        assert c.base_toughness == 4
        assert "Zombie" in c.subtypes

    def test_death_creates_two_zombie_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        twins = MaalfeldTwins(owner=p1, controller=p1)
        _place_on_battlefield(game, twins, p1)
        _simulate_death(game, twins, p1)
        bf = game.get_battlefield(p1).get_all()
        zombies = [c for c in bf if getattr(c, "name", "") == "Zombie"]
        assert len(zombies) == 2
        for z in zombies:
            assert z.base_power == 2
            assert z.base_toughness == 2


# ===================================================================
# DRAW ON DEATH
# ===================================================================


class TestSolemnSimulacrum:
    """Solemn Simulacrum — {4} 2/2 Golem — dies: draw a card."""

    def test_stats(self) -> None:
        c = SolemnSimulacrum()
        assert c.name == "Solemn Simulacrum"
        assert c.mana_cost == ManaCost.parse("{4}")
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert "Golem" in c.subtypes
        assert isinstance(c, ArtifactCreature)

    def test_death_draws_a_card(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        _place_on_battlefield(game, sim, p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_death(game, sim, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1


# ===================================================================
# MILL / SURVEIL ON DEATH
# ===================================================================


class TestCrowOfDarkTidings:
    """Crow of Dark Tidings — {2}{B} 2/1 Zombie Bird Flying — dies: mill 2."""

    def test_stats(self) -> None:
        c = CrowOfDarkTidings()
        assert c.name == "Crow of Dark Tidings"
        assert c.mana_cost == ManaCost.parse("{2}{B}")
        assert c.base_power == 2
        assert c.base_toughness == 1
        assert "Zombie" in c.subtypes
        assert "Bird" in c.subtypes
        assert Keyword.FLYING in c.keywords

    def test_death_mills_two_cards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        lib_cards = _add_cards_to_library(p1, 5)
        crow = CrowOfDarkTidings(owner=p1, controller=p1)
        _place_on_battlefield(game, crow, p1)
        lib_before = len(p1.zones[Zone.LIBRARY])
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _simulate_death(game, crow, p1)
        assert len(p1.zones[Zone.LIBRARY]) == lib_before - 2
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_before + 2


class TestWaryThespian:
    """Wary Thespian — {1}{G} 3/1 Cat Druid — dies: surveil 1."""

    def test_stats(self) -> None:
        c = WaryThespian()
        assert c.name == "Wary Thespian"
        assert c.mana_cost == ManaCost.parse("{1}{G}")
        assert c.base_power == 3
        assert c.base_toughness == 1
        assert "Cat" in c.subtypes
        assert "Druid" in c.subtypes

    def test_death_surveils_one(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        thespian = WaryThespian(owner=p1, controller=p1)
        _place_on_battlefield(game, thespian, p1)
        lib_before = len(p1.zones[Zone.LIBRARY])
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _simulate_death(game, thespian, p1)
        # Surveil 1 simplified: top card goes to graveyard
        assert len(p1.zones[Zone.LIBRARY]) == lib_before - 1
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_before + 1


# ===================================================================
# DRAIN / DAMAGE ON CREATURE DEATH
# ===================================================================


class TestVengefulBloodwitch:
    """Vengeful Bloodwitch — {1}{B} 1/1 Vampire Warlock — dies or another you control dies: drain 1."""

    def test_stats(self) -> None:
        c = VengefulBloodwitch()
        assert c.name == "Vengeful Bloodwitch"
        assert c.mana_cost == ManaCost.parse("{1}{B}")
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Vampire" in c.subtypes
        assert "Warlock" in c.subtypes

    def test_self_death_drains_opponent(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        witch = VengefulBloodwitch(owner=p1, controller=p1)
        _place_on_battlefield(game, witch, p1)
        p1_life = p1.life
        p2_life = p2.life
        _simulate_death(game, witch, p1)
        assert p1.life == p1_life + 1
        assert p2.life == p2_life - 1

    def test_another_creature_death_triggers(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        witch = VengefulBloodwitch(owner=p1, controller=p1)
        _place_on_battlefield(game, witch, p1)
        witch.register_triggers(game)

        other = Creature(name="Fodder", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        p2_life = p2.life
        _simulate_another_death(game, witch, other, p1)
        assert p1.life == p1_life + 1
        assert p2.life == p2_life - 1

    def test_opponent_creature_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        witch = VengefulBloodwitch(owner=p1, controller=p1)
        _place_on_battlefield(game, witch, p1)
        witch.register_triggers(game)

        enemy = Creature(name="Enemy", base_power=1, base_toughness=1, owner=p2, controller=p2)
        p1_life = p1.life
        _simulate_another_death(game, witch, enemy, p2)
        assert p1.life == p1_life  # no change


class TestMidnightReaper:
    """Midnight Reaper — {2}{B} 3/2 Zombie Knight — nontoken creature you control dies: deal 1 to you, draw."""

    def test_stats(self) -> None:
        c = MidnightReaper()
        assert c.name == "Midnight Reaper"
        assert c.mana_cost == ManaCost.parse("{2}{B}")
        assert c.base_power == 3
        assert c.base_toughness == 2
        assert "Zombie" in c.subtypes
        assert "Knight" in c.subtypes

    def test_nontoken_creature_death_deals_1_draws(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        reaper = MidnightReaper(owner=p1, controller=p1)
        _place_on_battlefield(game, reaper, p1)
        reaper.register_triggers(game)

        other = Creature(name="Fodder", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, reaper, other, p1)
        assert p1.life == p1_life - 1
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_token_creature_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        reaper = MidnightReaper(owner=p1, controller=p1)
        _place_on_battlefield(game, reaper, p1)
        reaper.register_triggers(game)

        token = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.is_token = True
        p1_life = p1.life
        _simulate_another_death(game, reaper, token, p1)
        assert p1.life == p1_life  # no damage, no draw


class TestHighSocietyHunter:
    """High-Society Hunter — {3}{B}{B} 5/3 Vampire Noble Flying — another nontoken dies: draw."""

    def test_stats(self) -> None:
        c = HighSocietyHunter()
        assert c.name == "High-Society Hunter"
        assert c.mana_cost == ManaCost.parse("{3}{B}{B}")
        assert c.base_power == 5
        assert c.base_toughness == 3
        assert "Vampire" in c.subtypes
        assert Keyword.FLYING in c.keywords

    def test_another_nontoken_dies_draws(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hunter.register_triggers(game)

        other = Creature(name="Victim", base_power=1, base_toughness=1, owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, hunter, other, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_self_death_does_not_trigger(self) -> None:
        """'another' — should not fire when self dies."""
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_death(game, hunter, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before

    def test_token_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hunter.register_triggers(game)

        token = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.is_token = True
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, hunter, token, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before


class TestGarnaBloodfistOfKeld:
    """Garna, Bloodfist of Keld — {1}{B}{R}{R} 4/3 Legendary Human Berserker."""

    def test_stats(self) -> None:
        c = GarnaBloodfistOfKeld()
        assert c.name == "Garna, Bloodfist of Keld"
        assert c.mana_cost == ManaCost.parse("{1}{B}{R}{R}")
        assert c.base_power == 4
        assert c.base_toughness == 3
        assert "Human" in c.subtypes
        assert "Berserker" in c.subtypes
        assert Supertype.LEGENDARY in c.supertypes

    def test_another_creature_death_deals_damage_to_opponents(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        garna = GarnaBloodfistOfKeld(owner=p1, controller=p1)
        _place_on_battlefield(game, garna, p1)
        garna.register_triggers(game)

        other = Creature(name="Soldier", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p2_life = p2.life
        _simulate_another_death(game, garna, other, p1)
        assert p2.life == p2_life - 1

    def test_self_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        garna = GarnaBloodfistOfKeld(owner=p1, controller=p1)
        _place_on_battlefield(game, garna, p1)
        p2_life = p2.life
        _simulate_death(game, garna, p1)
        assert p2.life == p2_life


class TestCrosswayTroublemakers:
    """Crossway Troublemakers — {5}{B} 5/5 Vampire — vampire dies: pay 2 life, draw."""

    def test_stats(self) -> None:
        c = CrosswayTroublemakers()
        assert c.name == "Crossway Troublemakers"
        assert c.mana_cost == ManaCost.parse("{5}{B}")
        assert c.base_power == 5
        assert c.base_toughness == 5
        assert "Vampire" in c.subtypes

    def test_vampire_death_pays_2_draws(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        ct = CrosswayTroublemakers(owner=p1, controller=p1)
        _place_on_battlefield(game, ct, p1)
        ct.register_triggers(game)

        vamp = Creature(name="Vamp", subtypes={"Vampire"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, ct, vamp, p1)
        assert p1.life == p1_life - 2
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_non_vampire_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        ct = CrosswayTroublemakers(owner=p1, controller=p1)
        _place_on_battlefield(game, ct, p1)
        ct.register_triggers(game)

        non_vamp = Creature(name="Human", subtypes={"Human"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        _simulate_another_death(game, ct, non_vamp, p1)
        assert p1.life == p1_life


class TestKalastriaHighborn:
    """Kalastria Highborn — {B}{B} 2/2 Vampire Shaman — self or vampire dies: drain 2."""

    def test_stats(self) -> None:
        c = KalastriaHighborn()
        assert c.name == "Kalastria Highborn"
        assert c.mana_cost == ManaCost.parse("{B}{B}")
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert "Vampire" in c.subtypes
        assert "Shaman" in c.subtypes

    def test_self_death_drains_2(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        kh = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, kh, p1)
        p1_life = p1.life
        p2_life = p2.life
        _simulate_death(game, kh, p1)
        assert p1.life == p1_life + 2
        assert p2.life == p2_life - 2

    def test_another_vampire_death_drains_2(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        kh = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, kh, p1)
        kh.register_triggers(game)

        vamp = Creature(name="Bat", subtypes={"Vampire"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        p2_life = p2.life
        _simulate_another_death(game, kh, vamp, p1)
        assert p1.life == p1_life + 2
        assert p2.life == p2_life - 2

    def test_non_vampire_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        kh = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, kh, p1)
        kh.register_triggers(game)

        human = Creature(name="Human", subtypes={"Human"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1_life = p1.life
        _simulate_another_death(game, kh, human, p1)
        assert p1.life == p1_life


# ===================================================================
# GRAVEYARD RECURSION ON DEATH
# ===================================================================


class TestDriverOfTheDead:
    """Driver of the Dead — {3}{B} 3/2 Vampire — dies: return creature with MV ≤2 from graveyard."""

    def test_stats(self) -> None:
        c = DriverOfTheDead()
        assert c.name == "Driver of the Dead"
        assert c.mana_cost == ManaCost.parse("{3}{B}")
        assert c.base_power == 3
        assert c.base_toughness == 2
        assert "Vampire" in c.subtypes

    def test_death_returns_low_cmc_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        driver = DriverOfTheDead(owner=p1, controller=p1)
        _place_on_battlefield(game, driver, p1)

        # Put a creature with cmc 2 in graveyard
        target = Creature(name="LowCost", mana_cost=ManaCost.parse("{1}{W}"),
                          base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)

        _simulate_death(game, driver, p1)
        bf = game.get_battlefield(p1).get_all()
        assert any(getattr(c, "name", "") == "LowCost" for c in bf)

    def test_death_skips_high_cmc_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        driver = DriverOfTheDead(owner=p1, controller=p1)
        _place_on_battlefield(game, driver, p1)

        expensive = Creature(name="BigGuy", mana_cost=ManaCost.parse("{4}{B}{B}"),
                             base_power=5, base_toughness=5, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(expensive)

        _simulate_death(game, driver, p1)
        bf = game.get_battlefield(p1).get_all()
        assert not any(getattr(c, "name", "") == "BigGuy" for c in bf)


class TestInfernalVessel:
    """Infernal Vessel — {2}{B} 2/1 Human Cleric — dies (if not Demon): return with +1/+1 counters, becomes Demon."""

    def test_stats(self) -> None:
        c = InfernalVessel()
        assert c.name == "Infernal Vessel"
        assert c.mana_cost == ManaCost.parse("{2}{B}")
        assert c.base_power == 2
        assert c.base_toughness == 1
        assert "Human" in c.subtypes
        assert "Cleric" in c.subtypes

    def test_death_returns_with_demon_subtype_and_counters(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        vessel = InfernalVessel(owner=p1, controller=p1)
        _place_on_battlefield(game, vessel, p1)
        # Put vessel in graveyard to simulate death
        p1.zones[Zone.GRAVEYARD].add(vessel)

        _simulate_death(game, vessel, p1)
        bf = game.get_battlefield(p1).get_all()
        # Should be on battlefield
        assert vessel in bf or any(getattr(c, "name", "") == "Infernal Vessel" for c in bf)
        assert "Demon" in vessel.subtypes
        # Should have two +1/+1 counters (stored as plus_one_counters attr)
        assert getattr(vessel, "plus_one_counters", 0) == 2

    def test_does_not_return_if_already_demon(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        vessel = InfernalVessel(owner=p1, controller=p1)
        vessel.subtypes = vessel.subtypes | {"Demon"}  # already a demon
        _place_on_battlefield(game, vessel, p1)
        p1.zones[Zone.GRAVEYARD].add(vessel)

        vessel.register_triggers(game)
        # Fire death - condition should not match since it's a Demon
        game.trigger_manager.fire_event(
            game,
            EventType.CREATURE_DIES,
            {"creature": vessel, "controller": p1},
        )
        # Stack should be empty (trigger condition not met)
        assert game.stack.is_empty()


class TestNineLivesFamiliar:
    """Nine-Lives Familiar — {1}{B}{B} 1/1 Cat — enters with 8 revival counters, dies: return with one fewer."""

    def test_stats(self) -> None:
        c = NineLivesFamiliar()
        assert c.name == "Nine-Lives Familiar"
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Cat" in c.subtypes
        assert c.revival_counters == 0  # starts at 0 before ETB

    def test_death_returns_with_fewer_counters(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        familiar = NineLivesFamiliar(owner=p1, controller=p1)
        familiar.revival_counters = 8  # simulate having entered via ETB
        _place_on_battlefield(game, familiar, p1)
        p1.zones[Zone.GRAVEYARD].add(familiar)

        _simulate_death(game, familiar, p1)
        bf = game.get_battlefield(p1).get_all()
        assert familiar in bf or any(getattr(c, "name", "") == "Nine-Lives Familiar" for c in bf)
        assert familiar.revival_counters == 7

    def test_death_does_not_return_with_zero_counters(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        familiar = NineLivesFamiliar(owner=p1, controller=p1)
        familiar.revival_counters = 0  # no counters left
        _place_on_battlefield(game, familiar, p1)
        p1.zones[Zone.GRAVEYARD].add(familiar)

        familiar.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EventType.CREATURE_DIES,
            {"creature": familiar, "controller": p1},
        )
        assert game.stack.is_empty()


class TestFiendishPanda:
    """Fiendish Panda — {2}{W}{B} 3/2 Bear Demon — dies: return non-Bear creature with MV ≤ power."""

    def test_stats(self) -> None:
        c = FiendishPanda()
        assert c.name == "Fiendish Panda"
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert c.base_power == 3
        assert c.base_toughness == 2
        assert "Bear" in c.subtypes
        assert "Demon" in c.subtypes

    def test_death_returns_non_bear_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        _place_on_battlefield(game, panda, p1)

        target = Creature(name="Knight", mana_cost=ManaCost.parse("{2}{W}"),
                          subtypes={"Knight"}, base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)

        _simulate_death(game, panda, p1)
        bf = game.get_battlefield(p1).get_all()
        assert any(getattr(c, "name", "") == "Knight" for c in bf)

    def test_death_skips_bear_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        _place_on_battlefield(game, panda, p1)

        bear = Creature(name="OtherBear", mana_cost=ManaCost.parse("{1}{G}"),
                        subtypes={"Bear"}, base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)

        _simulate_death(game, panda, p1)
        bf = game.get_battlefield(p1).get_all()
        assert not any(getattr(c, "name", "") == "OtherBear" for c in bf)


# ===================================================================
# SPINNER OF SOULS — library search on another death
# ===================================================================


class TestSpinnerOfSouls:
    """Spinner of Souls — {2}{G} 4/3 Spider Spirit Reach — another nontoken dies: reveal until creature, put in hand."""

    def test_stats(self) -> None:
        c = SpinnerOfSouls()
        assert c.name == "Spinner of Souls"
        assert c.mana_cost == ManaCost.parse("{2}{G}")
        assert c.base_power == 4
        assert c.base_toughness == 3
        assert "Spider" in c.subtypes
        assert "Spirit" in c.subtypes
        assert Keyword.REACH in c.keywords

    def test_another_nontoken_death_finds_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        _place_on_battlefield(game, spinner, p1)
        spinner.register_triggers(game)

        # Library: non-creature, non-creature, creature
        nc1 = CardImpl(name="Spell1", owner=p1)
        nc2 = CardImpl(name="Spell2", owner=p1)
        creature_in_lib = Creature(name="Found", base_power=1, base_toughness=1, owner=p1)
        # Add in order: creature at bottom, then non-creatures on top
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        p1.zones[Zone.LIBRARY].add(nc2)
        p1.zones[Zone.LIBRARY].add(nc1)

        other = Creature(name="Dying", base_power=1, base_toughness=1, owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, spinner, other, p1)

        hand = p1.zones[Zone.HAND].get_all()
        assert any(getattr(c, "name", "") == "Found" for c in hand)

    def test_self_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        _place_on_battlefield(game, spinner, p1)
        _add_cards_to_library(p1, 3)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_death(game, spinner, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before

    def test_token_death_does_not_trigger(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        _place_on_battlefield(game, spinner, p1)
        spinner.register_triggers(game)
        _add_cards_to_library(p1, 3)

        token = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.is_token = True
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_another_death(game, spinner, token, p1)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before


# ===================================================================
# REGISTRY
# ===================================================================


class TestRegistry:
    """register_death_trigger_creatures should register all 17 creatures."""

    ALL_NAMES = [
        "Infestation Sage",
        "Gleaming Barrier",
        "Maalfeld Twins",
        "Solemn Simulacrum",
        "Crow of Dark Tidings",
        "Wary Thespian",
        "Vengeful Bloodwitch",
        "Midnight Reaper",
        "High-Society Hunter",
        "Garna, Bloodfist of Keld",
        "Crossway Troublemakers",
        "Kalastria Highborn",
        "Driver of the Dead",
        "Infernal Vessel",
        "Nine-Lives Familiar",
        "Fiendish Panda",
        "Spinner of Souls",
    ]

    def test_all_registered(self) -> None:
        registry = CardRegistry()
        register_death_trigger_creatures(registry)
        for name in self.ALL_NAMES:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_count(self) -> None:
        registry = CardRegistry()
        register_death_trigger_creatures(registry)
        # Should have exactly 17 entries
        registered_count = sum(
            1 for name in self.ALL_NAMES if registry.get(name) is not None
        )
        assert registered_count == 17
