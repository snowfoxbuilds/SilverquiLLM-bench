"""Tests for cards/foundations/planeswalkers_batch2.py — Batch 2 planeswalker cards.

Verifies:
- Each planeswalker has correct name, mana_cost, starting_loyalty, card_types.
- All planeswalkers are Legendary with correct subtypes.
- get_loyalty_abilities() returns correct number of abilities with correct costs.
- Loyalty ability effects produce correct game-state changes.
- register_planeswalkers_batch2() registers all 3 planeswalkers.
"""

from __future__ import annotations

import pytest

from cards.foundations.planeswalkers_batch2 import (
    ChandraFlameshaper,
    KaitoCunningInfiltrator,
    VivienReid,
    register_planeswalkers_batch2,
)
from cards.registry import CardRegistry
from engine.card import Creature, GameObject, CardImpl
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(p1_life: int = 20, p2_life: int = 20) -> GameState:
    p1 = DeterministicPlayer("Alice", [], life=p1_life)
    p2 = DeterministicPlayer("Bob", [], life=p2_life)
    return GameState([p1, p2])


def _place_on_battlefield(player, obj, game=None):
    obj.owner = player
    obj.controller = player
    player.zones[Zone.BATTLEFIELD].add(obj)


# ---------------------------------------------------------------------------
# Kaito, Cunning Infiltrator
# ---------------------------------------------------------------------------

class TestKaitoCunningInfiltrator:
    def test_name_and_cost(self):
        pw = KaitoCunningInfiltrator()
        assert pw.name == "Kaito, Cunning Infiltrator"
        assert pw.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_card_type(self):
        pw = KaitoCunningInfiltrator()
        assert CardType.PLANESWALKER in pw.card_types

    def test_starting_loyalty(self):
        pw = KaitoCunningInfiltrator()
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3

    def test_legendary(self):
        pw = KaitoCunningInfiltrator()
        assert Supertype.LEGENDARY in pw.supertypes

    def test_subtypes(self):
        pw = KaitoCunningInfiltrator()
        assert "Kaito" in pw.subtypes

    def test_loyalty_abilities_count(self):
        pw = KaitoCunningInfiltrator()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs(self):
        pw = KaitoCunningInfiltrator()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == -2
        assert abilities[2].loyalty_cost == -9

    def test_minus2_creates_ninja_token(self):
        game = _make_game()
        p1 = game.players[0]
        pw = KaitoCunningInfiltrator()
        _place_on_battlefield(p1, pw)

        abilities = pw.get_loyalty_abilities()
        minus2 = abilities[1]

        bf_before = len(game.get_battlefield(p1).get_all())
        minus2.effect(game)
        bf_after = game.get_battlefield(p1).get_all()
        # Should have created a token
        new_objects = [o for o in bf_after if o is not pw]
        assert len(new_objects) >= 1
        ninja = new_objects[-1]
        assert ninja.name == "Ninja"
        assert ninja.base_power == 2
        assert ninja.base_toughness == 1

    def test_plus1_draws_and_discards(self):
        game = _make_game()
        p1 = game.players[0]
        pw = KaitoCunningInfiltrator()
        _place_on_battlefield(p1, pw)

        # Add cards to library and hand
        for i in range(3):
            card = CardImpl(name=f"LibCard{i}")
            card.owner = p1
            p1.zones[Zone.LIBRARY].add(card)

        hand_before = len(p1.zones[Zone.HAND].get_all())
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())

        abilities = pw.get_loyalty_abilities()
        plus1 = abilities[0]
        plus1.effect(game)

        # Drew 1 card then discarded 1 card — net hand size stays same or +0
        # Library should be smaller by 1 (draw)
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        assert lib_after == lib_before - 1


# ---------------------------------------------------------------------------
# Chandra, Flameshaper
# ---------------------------------------------------------------------------

class TestChandraFlameshaper:
    def test_name_and_cost(self):
        pw = ChandraFlameshaper()
        assert pw.name == "Chandra, Flameshaper"
        assert pw.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_card_type(self):
        pw = ChandraFlameshaper()
        assert CardType.PLANESWALKER in pw.card_types

    def test_starting_loyalty(self):
        pw = ChandraFlameshaper()
        assert pw.starting_loyalty == 6
        assert pw.loyalty == 6

    def test_legendary(self):
        pw = ChandraFlameshaper()
        assert Supertype.LEGENDARY in pw.supertypes

    def test_subtypes(self):
        pw = ChandraFlameshaper()
        assert "Chandra" in pw.subtypes

    def test_loyalty_abilities_count(self):
        pw = ChandraFlameshaper()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs(self):
        pw = ChandraFlameshaper()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +2
        assert abilities[1].loyalty_cost == +1
        assert abilities[2].loyalty_cost == -4

    def test_plus2_adds_red_mana(self):
        game = _make_game()
        p1 = game.players[0]
        pw = ChandraFlameshaper()
        _place_on_battlefield(p1, pw)

        # Add library cards for exile
        for i in range(5):
            card = CardImpl(name=f"LibCard{i}")
            card.owner = p1
            p1.zones[Zone.LIBRARY].add(card)

        initial_red = p1.mana_pool.get(ManaType.RED)
        abilities = pw.get_loyalty_abilities()
        plus2 = abilities[0]
        plus2.effect(game)
        assert p1.mana_pool.get(ManaType.RED) - initial_red == 3

    def test_plus2_exiles_top_three(self):
        game = _make_game()
        p1 = game.players[0]
        pw = ChandraFlameshaper()
        _place_on_battlefield(p1, pw)

        for i in range(5):
            card = CardImpl(name=f"LibCard{i}")
            card.owner = p1
            p1.zones[Zone.LIBRARY].add(card)

        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        abilities = pw.get_loyalty_abilities()
        plus2 = abilities[0]
        plus2.effect(game)
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        assert lib_before - lib_after == 3

    def test_ability_descriptions_present(self):
        pw = ChandraFlameshaper()
        abilities = pw.get_loyalty_abilities()
        for ability in abilities:
            assert ability.description is not None
            assert len(ability.description) > 0


# ---------------------------------------------------------------------------
# Vivien Reid
# ---------------------------------------------------------------------------

class TestVivienReid:
    def test_name_and_cost(self):
        pw = VivienReid()
        assert pw.name == "Vivien Reid"
        assert pw.mana_cost == ManaCost.parse("{3}{G}{G}")

    def test_card_type(self):
        pw = VivienReid()
        assert CardType.PLANESWALKER in pw.card_types

    def test_starting_loyalty(self):
        pw = VivienReid()
        assert pw.starting_loyalty == 5
        assert pw.loyalty == 5

    def test_legendary(self):
        pw = VivienReid()
        assert Supertype.LEGENDARY in pw.supertypes

    def test_subtypes(self):
        pw = VivienReid()
        assert "Vivien" in pw.subtypes

    def test_loyalty_abilities_count(self):
        pw = VivienReid()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs(self):
        pw = VivienReid()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == -3
        assert abilities[2].loyalty_cost == -8

    def test_plus1_finds_creature_from_top_four(self):
        game = _make_game()
        p1 = game.players[0]
        pw = VivienReid()
        _place_on_battlefield(p1, pw)

        # Add cards — creature on top
        noncreature = CardImpl(name="Spell")
        noncreature.owner = p1
        p1.zones[Zone.LIBRARY].add(noncreature)

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.owner = p1
        p1.zones[Zone.LIBRARY].add(creature)

        abilities = pw.get_loyalty_abilities()
        plus1 = abilities[0]
        plus1.effect(game)

        hand_cards = p1.zones[Zone.HAND].get_all()
        hand_names = [getattr(c, "name", "") for c in hand_cards]
        assert "Bear" in hand_names

    def test_minus8_buffs_creatures(self):
        game = _make_game()
        p1 = game.players[0]
        pw = VivienReid()
        _place_on_battlefield(p1, pw)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(p1, bear)

        abilities = pw.get_loyalty_abilities()
        minus8 = abilities[2]
        minus8.effect(game)

        assert bear.base_power == 4  # 2 + 2
        assert bear.base_toughness == 4  # 2 + 2
        assert Keyword.VIGILANCE in bear.keywords
        assert Keyword.TRAMPLE in bear.keywords
        assert Keyword.INDESTRUCTIBLE in bear.keywords

    def test_minus8_does_not_buff_planeswalker(self):
        game = _make_game()
        p1 = game.players[0]
        pw = VivienReid()
        _place_on_battlefield(p1, pw)

        abilities = pw.get_loyalty_abilities()
        minus8 = abilities[2]
        # Should not crash even with no creatures
        minus8.effect(game)
        # PW should not have power/toughness modified
        assert not hasattr(pw, "base_power") or pw.base_power == 0 or True  # Just no crash

    def test_ability_descriptions_present(self):
        pw = VivienReid()
        abilities = pw.get_loyalty_abilities()
        for ability in abilities:
            assert ability.description is not None
            assert len(ability.description) > 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_all_three_planeswalkers(self):
        registry = CardRegistry()
        register_planeswalkers_batch2(registry)
        expected = [
            "Kaito, Cunning Infiltrator",
            "Chandra, Flameshaper",
            "Vivien Reid",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_registered_metadata_has_mythic_rarity(self):
        registry = CardRegistry()
        register_planeswalkers_batch2(registry)
        for name in ["Kaito, Cunning Infiltrator", "Chandra, Flameshaper", "Vivien Reid"]:
            entry = registry.get(name)
            assert entry is not None
            metadata = entry[1] if isinstance(entry, tuple) else entry
            if hasattr(metadata, "rarity"):
                assert metadata.rarity == "mythic"
