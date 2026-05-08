"""Tests for cards/foundations/modal_spells.py — Modal spell cards.

Verifies:
- Each modal spell has the correct name, mana_cost, and card_types.
- get_modes() returns the correct number of Mode objects.
- Each Mode has a non-empty name and description.
- Instants have CardType.INSTANT, sorceries have CardType.SORCERY.
- register_modal_spells() registers all 8 modal spells in the registry.
- on_resolve() produces the correct game effects for each chosen mode.
"""

from __future__ import annotations

import pytest

from cards.foundations.modal_spells import (
    AbzanCharm,
    AustereCommand,
    BorosCharm,
    CollectiveBrutality,
    DromokasCommand,
    InscriptionOfInsight,
    PrismariCommand,
    SublimeEpiphany,
    register_modal_spells,
)
from cards.registry import CardRegistry
from engine.card import Creature, Enchantment, Mode
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, ManaCost, Zone


# ---------------------------------------------------------------------------
# Helpers for behaviour tests
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


def _put_in_library(player, card):
    """Add *card* to the top of *player*'s library."""
    card.owner = player
    player.zones[Zone.LIBRARY].add(card)


# ---------------------------------------------------------------------------
# Choose-one instants
# ---------------------------------------------------------------------------

class TestAbzanCharm:
    def test_name_and_cost(self):
        card = AbzanCharm()
        assert card.name == "Abzan Charm"
        assert card.mana_cost == ManaCost.parse("{W}{B}{G}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        card = AbzanCharm()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_modes_have_content(self):
        card = AbzanCharm()
        for mode in card.get_modes():
            assert mode.name
            assert mode.description


class TestBorosCharm:
    def test_name_and_cost(self):
        card = BorosCharm()
        assert card.name == "Boros Charm"
        assert card.mana_cost == ManaCost.parse("{R}{W}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        card = BorosCharm()
        assert len(card.get_modes()) == 3


class TestPrismariCommand:
    def test_name_and_cost(self):
        card = PrismariCommand()
        assert card.name == "Prismari Command"
        assert card.mana_cost == ManaCost.parse("{1}{U}{R}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        card = PrismariCommand()
        assert len(card.get_modes()) == 4


class TestSublimeEpiphany:
    def test_name_and_cost(self):
        card = SublimeEpiphany()
        assert card.name == "Sublime Epiphany"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        card = SublimeEpiphany()
        assert len(card.get_modes()) == 5


# ---------------------------------------------------------------------------
# Choose-two / choose-more sorceries
# ---------------------------------------------------------------------------

class TestDromokasCommand:
    def test_name_and_cost(self):
        card = DromokasCommand()
        assert card.name == "Dromoka's Command"
        assert card.mana_cost == ManaCost.parse("{G}{W}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        card = DromokasCommand()
        assert len(card.get_modes()) == 4


class TestAustereCommand:
    def test_name_and_cost(self):
        card = AustereCommand()
        assert card.name == "Austere Command"
        assert card.mana_cost == ManaCost.parse("{4}{W}{W}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        card = AustereCommand()
        assert len(card.get_modes()) == 4


class TestCollectiveBrutality:
    def test_name_and_cost(self):
        card = CollectiveBrutality()
        assert card.name == "Collective Brutality"
        assert card.mana_cost == ManaCost.parse("{1}{B}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        card = CollectiveBrutality()
        assert len(card.get_modes()) == 3


class TestInscriptionOfInsight:
    def test_name_and_cost(self):
        card = InscriptionOfInsight()
        assert card.name == "Inscription of Insight"
        assert card.mana_cost == ManaCost.parse("{3}{U}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        card = InscriptionOfInsight()
        assert len(card.get_modes()) == 3


# ---------------------------------------------------------------------------
# Behaviour: Abzan Charm on_resolve
# ---------------------------------------------------------------------------

class TestAbzanCharmResolve:
    def test_mode1_draw_two_lose_two(self):
        """Mode 1: controller draws 2 cards and loses 2 life."""
        game = _make_game()
        alice = game.players[0]
        # Stock library with 2 cards
        _put_in_library(alice, Creature(name="Card A"))
        _put_in_library(alice, Creature(name="Card B"))

        charm = AbzanCharm()
        charm.controller = alice
        charm.chosen_mode = 1
        charm.on_resolve(game)

        assert len(game.get_hand(alice).get_all()) == 2
        assert alice.life == 18

    def test_mode2_distribute_counters(self):
        """Mode 2: distribute two +1/+1 counters among targets."""
        game = _make_game()
        alice = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(alice, bear)

        charm = AbzanCharm()
        charm.controller = alice
        charm.chosen_mode = 2
        charm.chosen_targets = [bear]
        charm.on_resolve(game)

        assert bear.plus_one_counters == 2
        assert bear.power == 4
        assert bear.toughness == 4


# ---------------------------------------------------------------------------
# Behaviour: Boros Charm on_resolve
# ---------------------------------------------------------------------------

class TestBorosCharmResolve:
    def test_mode0_deal_4_damage_to_player(self):
        """Mode 0: deal 4 damage to target player."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]

        charm = BorosCharm()
        charm.controller = alice
        charm.chosen_mode = 0
        charm.chosen_targets = [bob]
        charm.on_resolve(game)

        assert bob.life == 16

    def test_mode2_double_strike(self):
        """Mode 2: target creature gains double strike."""
        from engine.types import Keyword
        game = _make_game()
        alice = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(alice, bear)

        charm = BorosCharm()
        charm.controller = alice
        charm.chosen_mode = 2
        charm.chosen_targets = [bear]
        charm.on_resolve(game)

        assert Keyword.DOUBLE_STRIKE in bear.keywords


# ---------------------------------------------------------------------------
# Behaviour: Prismari Command on_resolve
# ---------------------------------------------------------------------------

class TestPrismariCommandResolve:
    def test_mode0_deal_2_damage(self):
        """Mode 0: deal 2 damage to target player."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]

        cmd = PrismariCommand()
        cmd.controller = alice
        cmd.chosen_modes = [0]
        cmd.chosen_targets = [bob]
        cmd.on_resolve(game)

        assert bob.life == 18

    def test_mode1_create_treasure(self):
        """Mode 1: create a Treasure artifact token."""
        game = _make_game()
        alice = game.players[0]

        cmd = PrismariCommand()
        cmd.controller = alice
        cmd.chosen_modes = [1]
        cmd.on_resolve(game)

        bf = game.get_battlefield(alice).get_all()
        treasures = [o for o in bf if getattr(o, "name", "") == "Treasure"]
        assert len(treasures) == 1


# ---------------------------------------------------------------------------
# Behaviour: Sublime Epiphany on_resolve
# ---------------------------------------------------------------------------

class TestSublimeEpiphanyResolve:
    def test_mode3_draw_card(self):
        """Mode 3: controller draws a card."""
        game = _make_game()
        alice = game.players[0]
        _put_in_library(alice, Creature(name="Card"))

        spell = SublimeEpiphany()
        spell.controller = alice
        spell.chosen_modes = [3]
        spell.on_resolve(game)

        assert len(game.get_hand(alice).get_all()) == 1

    def test_mode4_bounce_nonland(self):
        """Mode 4: return target nonland permanent to owner's hand."""
        game = _make_game()
        bob = game.players[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(bob, bear)

        spell = SublimeEpiphany()
        spell.controller = game.players[0]
        spell.chosen_modes = [4]
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should be gone from battlefield, in Bob's hand
        assert not game.get_battlefield(bob).contains(bear)
        assert game.get_hand(bob).contains(bear)


# ---------------------------------------------------------------------------
# Behaviour: Dromoka's Command on_resolve
# ---------------------------------------------------------------------------

class TestDromokasCommandResolve:
    def test_mode0_plus_one_counter(self):
        """Mode 0: put a +1/+1 counter on target creature."""
        game = _make_game()
        alice = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(alice, bear)

        cmd = DromokasCommand()
        cmd.controller = alice
        cmd.chosen_modes = [0]
        cmd.chosen_targets = [bear]
        cmd.on_resolve(game)

        assert bear.plus_one_counters == 1
        assert bear.power == 3


# ---------------------------------------------------------------------------
# Behaviour: Austere Command on_resolve
# ---------------------------------------------------------------------------

class TestAustereCommandResolve:
    def test_destroy_all_enchantments(self):
        """Mode 1: destroy all enchantments on the battlefield."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        ench_a = Enchantment(name="Aura A")
        ench_b = Enchantment(name="Aura B")
        _place_on_battlefield(alice, ench_a)
        _place_on_battlefield(bob, ench_b)

        cmd = AustereCommand()
        cmd.controller = alice
        cmd.chosen_modes = [1]
        cmd.on_resolve(game)

        assert not game.get_battlefield(alice).contains(ench_a)
        assert not game.get_battlefield(bob).contains(ench_b)


# ---------------------------------------------------------------------------
# Behaviour: Collective Brutality on_resolve
# ---------------------------------------------------------------------------

class TestCollectiveBrutalityResolve:
    def test_mode2_drain(self):
        """Mode 2: opponent loses 2 life and you gain 2 life."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]

        spell = CollectiveBrutality()
        spell.controller = alice
        spell.chosen_modes = [2]
        spell.chosen_targets = [bob]
        spell.on_resolve(game)

        assert bob.life == 18
        assert alice.life == 22

    def test_mode1_shrink(self):
        """Mode 1: target creature gets -2/-2."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _place_on_battlefield(bob, bear)

        spell = CollectiveBrutality()
        spell.controller = alice
        spell.chosen_modes = [1]
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.base_power == 0
        assert bear.base_toughness == 0


# ---------------------------------------------------------------------------
# Behaviour: Inscription of Insight on_resolve
# ---------------------------------------------------------------------------

class TestInscriptionOfInsightResolve:
    def test_mode1_draw_two(self):
        """Mode 1: scry 2 then draw 2 (simplified to draw 2)."""
        game = _make_game()
        alice = game.players[0]
        _put_in_library(alice, Creature(name="C1"))
        _put_in_library(alice, Creature(name="C2"))

        spell = InscriptionOfInsight()
        spell.controller = alice
        spell.chosen_modes = [1]
        spell.on_resolve(game)

        assert len(game.get_hand(alice).get_all()) == 2

    def test_mode2_create_illusion_token(self):
        """Mode 2: create X/X Illusion token where X = cards in hand."""
        game = _make_game()
        alice = game.players[0]
        # Put 3 cards in hand to make X = 3
        for i in range(3):
            game.get_hand(alice).add(Creature(name=f"H{i}"))

        spell = InscriptionOfInsight()
        spell.controller = alice
        spell.chosen_modes = [2]
        spell.on_resolve(game)

        bf = game.get_battlefield(alice).get_all()
        illusions = [o for o in bf if getattr(o, "name", "") == "Illusion"]
        assert len(illusions) == 1
        assert illusions[0].base_power == 3
        assert illusions[0].base_toughness == 3


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_modal_spells_count(self):
        registry = CardRegistry()
        register_modal_spells(registry)
        assert len(registry) == 8

    def test_registered_names(self):
        registry = CardRegistry()
        register_modal_spells(registry)
        expected = {
            "Abzan Charm", "Boros Charm", "Prismari Command",
            "Sublime Epiphany", "Dromoka's Command", "Austere Command",
            "Collective Brutality", "Inscription of Insight",
        }
        assert set(registry.list_all()) == expected
