"""Tests for cards/foundations/planeswalkers.py — Planeswalker cards.

Verifies:
- Each planeswalker has correct name, mana_cost, starting_loyalty, card_types.
- All planeswalkers are Legendary.
- get_loyalty_abilities() returns the correct number of abilities.
- Loyalty abilities have correct loyalty_cost values.
- register_planeswalkers() registers all 4 planeswalkers in the registry.
- Loyalty ability effects produce the correct game-state changes.
"""

from __future__ import annotations

import pytest

from cards.foundations.planeswalkers import (
    AjaniCallerOfThePride,
    ChandraTorchOfDefiance,
    LilianaDreadhordeGeneral,
    NissaWorldwaker,
    register_planeswalkers,
)
from cards.registry import CardRegistry
from engine.card import Creature, Planeswalker, GameObject
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, ManaCost, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(p1_life: int = 20, p2_life: int = 20) -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [], life=p1_life)
    p2 = DeterministicPlayer("Bob", [], life=p2_life)
    return GameState([p1, p2])


def _place_on_battlefield(player, obj):
    """Put *obj* on *player*'s battlefield and set owner/controller."""
    obj.owner = player
    obj.controller = player
    player.zones[Zone.BATTLEFIELD].add(obj)


# ---------------------------------------------------------------------------
# Ajani
# ---------------------------------------------------------------------------

class TestAjaniCallerOfThePride:
    def test_name_and_cost(self):
        pw = AjaniCallerOfThePride()
        assert pw.name == "Ajani, Caller of the Pride"
        assert pw.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert CardType.PLANESWALKER in pw.card_types

    def test_starting_loyalty(self):
        pw = AjaniCallerOfThePride()
        assert pw.starting_loyalty == 4
        assert pw.loyalty == 4

    def test_legendary(self):
        pw = AjaniCallerOfThePride()
        assert Supertype.LEGENDARY in pw.supertypes

    def test_subtypes(self):
        pw = AjaniCallerOfThePride()
        assert "Ajani" in pw.subtypes

    def test_loyalty_abilities_count(self):
        pw = AjaniCallerOfThePride()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs(self):
        pw = AjaniCallerOfThePride()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == -3
        assert abilities[2].loyalty_cost == -8


# ---------------------------------------------------------------------------
# Chandra
# ---------------------------------------------------------------------------

class TestChandraTorchOfDefiance:
    def test_name_and_cost(self):
        pw = ChandraTorchOfDefiance()
        assert pw.name == "Chandra, Torch of Defiance"
        assert pw.mana_cost == ManaCost.parse("{2}{R}{R}")

    def test_starting_loyalty(self):
        pw = ChandraTorchOfDefiance()
        assert pw.starting_loyalty == 4
        assert pw.loyalty == 4

    def test_legendary(self):
        pw = ChandraTorchOfDefiance()
        assert Supertype.LEGENDARY in pw.supertypes

    def test_loyalty_abilities_count(self):
        pw = ChandraTorchOfDefiance()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self):
        pw = ChandraTorchOfDefiance()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == +1
        assert abilities[2].loyalty_cost == -3
        assert abilities[3].loyalty_cost == -7


# ---------------------------------------------------------------------------
# Liliana
# ---------------------------------------------------------------------------

class TestLilianaDreadhordeGeneral:
    def test_name_and_cost(self):
        pw = LilianaDreadhordeGeneral()
        assert pw.name == "Liliana, Dreadhorde General"
        assert pw.mana_cost == ManaCost.parse("{4}{B}{B}")

    def test_starting_loyalty(self):
        pw = LilianaDreadhordeGeneral()
        assert pw.starting_loyalty == 6
        assert pw.loyalty == 6

    def test_loyalty_abilities_count(self):
        pw = LilianaDreadhordeGeneral()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3


# ---------------------------------------------------------------------------
# Nissa
# ---------------------------------------------------------------------------

class TestNissaWorldwaker:
    def test_name_and_cost(self):
        pw = NissaWorldwaker()
        assert pw.name == "Nissa, Worldwaker"
        assert pw.mana_cost == ManaCost.parse("{3}{G}{G}")

    def test_starting_loyalty(self):
        pw = NissaWorldwaker()
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3

    def test_loyalty_abilities_count(self):
        pw = NissaWorldwaker()
        abilities = pw.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs(self):
        pw = NissaWorldwaker()
        abilities = pw.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == +1
        assert abilities[2].loyalty_cost == -7


# ---------------------------------------------------------------------------
# Ability activation: Ajani
# ---------------------------------------------------------------------------

class TestAjaniAbilityEffects:
    def test_plus1_adds_counter(self):
        """Ajani +1: Put a +1/+1 counter on target creature."""
        game = _make_game()
        alice = game.players[0]
        pw = AjaniCallerOfThePride()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(alice, bear)
        pw._resolve_target = bear

        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +1 effect

        assert bear.plus_one_counters == 1
        assert bear.power == 3
        assert bear.toughness == 3

    def test_minus3_grants_flying_double_strike(self):
        """Ajani -3: Target creature gains flying and double strike."""
        from engine.types import Keyword
        game = _make_game()
        alice = game.players[0]
        pw = AjaniCallerOfThePride()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(alice, bear)
        pw._resolve_target = bear

        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)  # -3 effect

        assert Keyword.FLYING in bear.keywords
        assert Keyword.DOUBLE_STRIKE in bear.keywords

    def test_minus8_creates_cat_tokens(self):
        """Ajani -8: Create X 2/2 Cat tokens where X = your life."""
        game = _make_game(p1_life=5)
        alice = game.players[0]
        pw = AjaniCallerOfThePride()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        abilities = pw.get_loyalty_abilities()
        abilities[2].effect(game)  # -8 effect

        bf = game.get_battlefield(alice).get_all()
        cats = [o for o in bf if getattr(o, "name", "") == "Cat"]
        assert len(cats) == 5
        assert all(c.base_power == 2 and c.base_toughness == 2 for c in cats)


# ---------------------------------------------------------------------------
# Ability activation: Chandra
# ---------------------------------------------------------------------------

class TestChandraAbilityEffects:
    def test_plus1_exile_deals_damage_to_opponents(self):
        """Chandra +1 (exile): deals 2 damage to each opponent."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        pw = ChandraTorchOfDefiance()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +1 exile/damage

        assert bob.life == 18
        assert alice.life == 20  # controller unaffected

    def test_plus1_mana_adds_red(self):
        """Chandra +1 (mana): add {R}{R} to controller's mana pool."""
        from engine.types import ManaType
        game = _make_game()
        alice = game.players[0]
        pw = ChandraTorchOfDefiance()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)  # +1 mana

        assert alice.mana_pool.get(ManaType.RED) >= 2

    def test_minus3_deals_4_damage_to_creature(self):
        """Chandra -3: deal 4 damage to target creature."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        pw = ChandraTorchOfDefiance()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(bob, bear)
        pw._resolve_target = bear

        abilities = pw.get_loyalty_abilities()
        abilities[2].effect(game)  # -3 damage

        assert bear.damage_marked == 4


# ---------------------------------------------------------------------------
# Ability activation: Liliana
# ---------------------------------------------------------------------------

class TestLilianaAbilityEffects:
    def test_plus1_opponent_sacrifices_creature(self):
        """Liliana +1: each opponent sacrifices a creature."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        pw = LilianaDreadhordeGeneral()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        goblin = Creature(name="Goblin", base_power=1, base_toughness=1)
        _place_on_battlefield(bob, goblin)

        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +1 sacrifice

        assert not game.get_battlefield(bob).contains(goblin)

    def test_minus4_draw_cards_equal_to_creatures(self):
        """Liliana -4: each player draws cards equal to creatures they control."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        pw = LilianaDreadhordeGeneral()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        # Alice controls 1 creature, Bob controls 2
        _place_on_battlefield(alice, Creature(name="Zombie"))
        _place_on_battlefield(bob, Creature(name="Soldier 1"))
        _place_on_battlefield(bob, Creature(name="Soldier 2"))

        # Stock libraries
        for _ in range(3):
            alice.zones[Zone.LIBRARY].add(Creature(name="LibA"))
            bob.zones[Zone.LIBRARY].add(Creature(name="LibB"))

        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)  # -4 draw

        # Alice controls 1 creature -> draws 1; Bob controls 2 -> draws 2
        assert len(game.get_hand(alice).get_all()) == 1
        assert len(game.get_hand(bob).get_all()) == 2


# ---------------------------------------------------------------------------
# Ability activation: Nissa
# ---------------------------------------------------------------------------

class TestNissaAbilityEffects:
    def test_plus1_animate_land(self):
        """Nissa +1: target land becomes a 4/4 creature."""
        from engine.card import Land
        game = _make_game()
        alice = game.players[0]
        pw = NissaWorldwaker()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        forest = Land(name="Forest")
        _place_on_battlefield(alice, forest)
        pw._resolve_target = forest

        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +1 animate

        assert forest.base_power == 4
        assert forest.base_toughness == 4

    def test_plus1_untap_lands(self):
        """Nissa +1: untap up to four tapped lands."""
        from engine.card import Land
        game = _make_game()
        alice = game.players[0]
        pw = NissaWorldwaker()
        pw.controller = alice
        _place_on_battlefield(alice, pw)

        lands = []
        for i in range(4):
            land = Land(name=f"Forest {i}")
            land.is_tapped = True
            _place_on_battlefield(alice, land)
            lands.append(land)

        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)  # +1 untap

        untapped = [l for l in lands if not l.is_tapped]
        assert len(untapped) == 4


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_planeswalkers_count(self):
        registry = CardRegistry()
        register_planeswalkers(registry)
        assert len(registry) == 4

    def test_registered_names(self):
        registry = CardRegistry()
        register_planeswalkers(registry)
        expected = {
            "Ajani, Caller of the Pride",
            "Chandra, Torch of Defiance",
            "Liliana, Dreadhorde General",
            "Nissa, Worldwaker",
        }
        assert set(registry.list_all()) == expected
