"""Tests for cards/foundations/complex_spells.py — Modal, X-cost, and kicker spells.

Verifies:
- Each card's metadata (name, mana_cost, card_types, power/toughness for creatures).
- Modal spells: get_modes() returns correct Mode objects; each mode resolves correctly.
- Modal creatures: ETB modes work (counters, life gain, flicker).
- X-cost spells: effects scale with x_value; X=0 edge case.
- Kicker spells: base vs kicked effects differ.
- Edge cases: mode not chosen (None), X=0.
- Registration: register_complex_spells() populates registry with all 16 cards.
"""

from __future__ import annotations

import pytest

from cards.foundations.complex_spells import (
    Abrade,
    ApothecaryStomper,
    Bushwhack,
    BurstLightning,
    CharmingPrince,
    DeadlyPlot,
    Exsanguinate,
    FinaleOfRevelation,
    GatekeeperOfMalakir,
    GnarlidColony,
    GoblinSurprise,
    IntoTheRoil,
    PrimalMight,
    SeekersFolly,
    Slagstorm,
    ValorousStance,
    register_complex_spells,
)
from cards.registry import CardRegistry
from engine.card import Creature, Mode
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(p1_life: int = 20, p2_life: int = 20) -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [], life=p1_life)
    p2 = DeterministicPlayer("Bob", [], life=p2_life)
    return GameState([p1, p2])


def _place_on_battlefield(game, player, obj):
    """Put *obj* on *player*'s battlefield and set owner/controller."""
    obj.owner = player
    obj.controller = player
    game.get_battlefield(player).add(obj)


def _put_in_hand(game, player, card):
    card.owner = player
    game.get_hand(player).add(card)


def _put_in_library(player, card):
    card.owner = player
    player.zones[Zone.LIBRARY].add(card)


def _put_in_graveyard(game, player, card):
    card.owner = player
    player.zones[Zone.GRAVEYARD].add(card)


def _make_creature(name="Bear", power=2, toughness=2, **kwargs):
    return Creature(name=name, base_power=power, base_toughness=toughness, **kwargs)


def _fire_etb_and_resolve(game, permanent):
    """Fire ENTERS_BATTLEFIELD event and resolve the resulting stack objects."""
    from engine.triggers import EventType
    game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": permanent})
    # Resolve any triggered abilities pushed to the stack
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ===========================================================================
# METADATA TESTS
# ===========================================================================


class TestAbradeMetadata:
    def test_name_and_cost(self):
        card = Abrade()
        assert card.name == "Abrade"
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_card_type(self):
        card = Abrade()
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        card = Abrade()
        modes = card.get_modes()
        assert len(modes) == 2
        assert all(isinstance(m, Mode) for m in modes)


class TestValorousStanceMetadata:
    def test_name_and_cost(self):
        card = ValorousStance()
        assert card.name == "Valorous Stance"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        assert len(ValorousStance().get_modes()) == 2


class TestGoblinSurpriseMetadata:
    def test_name_and_cost(self):
        card = GoblinSurprise()
        assert card.name == "Goblin Surprise"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        assert len(GoblinSurprise().get_modes()) == 2


class TestDeadlyPlotMetadata:
    def test_name_and_cost(self):
        card = DeadlyPlot()
        assert card.name == "Deadly Plot"
        assert card.mana_cost == ManaCost.parse("{3}{B}")
        assert CardType.INSTANT in card.card_types

    def test_modes_count(self):
        assert len(DeadlyPlot().get_modes()) == 2


class TestSlagstormMetadata:
    def test_name_and_cost(self):
        card = Slagstorm()
        assert card.name == "Slagstorm"
        assert card.mana_cost == ManaCost.parse("{1}{R}{R}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        assert len(Slagstorm().get_modes()) == 2


class TestBushwhackMetadata:
    def test_name_and_cost(self):
        card = Bushwhack()
        assert card.name == "Bushwhack"
        assert card.mana_cost == ManaCost.parse("{G}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        assert len(Bushwhack().get_modes()) == 2


class TestSeekersFollyMetadata:
    def test_name_and_cost(self):
        card = SeekersFolly()
        assert card.name == "Seeker's Folly"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert CardType.SORCERY in card.card_types

    def test_modes_count(self):
        assert len(SeekersFolly().get_modes()) == 2


class TestApothecaryStomperMetadata:
    def test_name_cost_stats(self):
        card = ApothecaryStomper()
        assert card.name == "Apothecary Stomper"
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")
        assert CardType.CREATURE in card.card_types
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_vigilance(self):
        card = ApothecaryStomper()
        assert Keyword.VIGILANCE in card.keywords

    def test_modes_count(self):
        assert len(ApothecaryStomper().get_modes()) == 2


class TestCharmingPrinceMetadata:
    def test_name_cost_stats(self):
        card = CharmingPrince()
        assert card.name == "Charming Prince"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_modes_count(self):
        assert len(CharmingPrince().get_modes()) == 3


class TestExsanguinateMetadata:
    def test_name_and_cost(self):
        card = Exsanguinate()
        assert card.name == "Exsanguinate"
        assert CardType.SORCERY in card.card_types

    def test_x_value_default(self):
        assert Exsanguinate().x_value == 0


class TestPrimalMightMetadata:
    def test_name_and_cost(self):
        card = PrimalMight()
        assert card.name == "Primal Might"
        assert CardType.SORCERY in card.card_types

    def test_x_value_default(self):
        assert PrimalMight().x_value == 0


class TestFinaleOfRevelationMetadata:
    def test_name_and_cost(self):
        card = FinaleOfRevelation()
        assert card.name == "Finale of Revelation"
        assert CardType.SORCERY in card.card_types

    def test_x_value_default(self):
        assert FinaleOfRevelation().x_value == 0


class TestBurstLightningMetadata:
    def test_name_and_cost(self):
        card = BurstLightning()
        assert card.name == "Burst Lightning"
        assert card.mana_cost == ManaCost.parse("{R}")
        assert CardType.INSTANT in card.card_types

    def test_kicked_default_false(self):
        assert BurstLightning().kicked is False

    def test_has_kicker_cost(self):
        assert BurstLightning().kicker_cost == ManaCost.parse("{4}")


class TestIntoTheRoilMetadata:
    def test_name_and_cost(self):
        card = IntoTheRoil()
        assert card.name == "Into the Roil"
        assert card.mana_cost == ManaCost.parse("{1}{U}")
        assert CardType.INSTANT in card.card_types

    def test_kicked_default_false(self):
        assert IntoTheRoil().kicked is False


class TestGnarlidColonyMetadata:
    def test_name_cost_stats(self):
        card = GnarlidColony()
        assert card.name == "Gnarlid Colony"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 2
        assert CardType.CREATURE in card.card_types

    def test_kicked_default_false(self):
        assert GnarlidColony().kicked is False


class TestGatekeeperOfMalakirMetadata:
    def test_name_cost_stats(self):
        card = GatekeeperOfMalakir()
        assert card.name == "Gatekeeper of Malakir"
        assert card.mana_cost == ManaCost.parse("{B}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_kicked_default_false(self):
        assert GatekeeperOfMalakir().kicked is False


# ===========================================================================
# MODAL SPELL BEHAVIOUR TESTS
# ===========================================================================


class TestAbradeResolve:
    def test_mode0_deals_3_damage_to_creature(self):
        """Mode 0: deal 3 damage to target creature."""
        game = _make_game()
        alice = game.players[0]
        bear = _make_creature("Bear", 2, 5)
        _place_on_battlefield(game, alice, bear)

        spell = Abrade()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.damage_marked == 3

    def test_mode1_destroys_artifact(self):
        """Mode 1: destroy target artifact."""
        from engine.card import Artifact
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        art = Artifact(name="Sol Ring")
        _place_on_battlefield(game, bob, art)

        spell = Abrade()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.chosen_targets = [art]
        spell.on_resolve(game)

        assert not game.get_battlefield(bob).contains(art)

    def test_no_mode_chosen_does_nothing(self):
        """If chosen_mode is None, on_resolve should be a no-op."""
        game = _make_game()
        spell = Abrade()
        spell.controller = game.players[0]
        spell.chosen_mode = None
        spell.on_resolve(game)  # Should not raise


class TestValorousStanceResolve:
    def test_mode0_grants_indestructible(self):
        game = _make_game()
        alice = game.players[0]
        bear = _make_creature()
        _place_on_battlefield(game, alice, bear)

        spell = ValorousStance()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.INDESTRUCTIBLE in bear.keywords

    def test_mode1_destroys_creature_with_toughness_4_plus(self):
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        big = _make_creature("Giant", 5, 5)
        _place_on_battlefield(game, bob, big)

        spell = ValorousStance()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.chosen_targets = [big]
        spell.on_resolve(game)

        assert not game.get_battlefield(bob).contains(big)

    def test_mode1_does_not_destroy_small_creature(self):
        """Toughness < 4 creatures should NOT be destroyed."""
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        small = _make_creature("Squire", 1, 2)
        _place_on_battlefield(game, bob, small)

        spell = ValorousStance()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.chosen_targets = [small]
        spell.on_resolve(game)

        assert game.get_battlefield(bob).contains(small)


class TestGoblinSurpriseResolve:
    def test_mode0_pumps_creatures(self):
        """Mode 0: creatures you control get +2/+0."""
        game = _make_game()
        alice = game.players[0]
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, alice, bear)

        spell = GoblinSurprise()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.on_resolve(game)

        assert bear.base_power == 4

    def test_mode1_creates_two_goblin_tokens(self):
        """Mode 1: create two 1/1 Goblin tokens."""
        game = _make_game()
        alice = game.players[0]

        spell = GoblinSurprise()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.on_resolve(game)

        bf = game.get_battlefield(alice).get_all()
        goblins = [o for o in bf if getattr(o, "name", "") == "Goblin"]
        assert len(goblins) == 2
        assert all(g.base_power == 1 and g.base_toughness == 1 for g in goblins)


class TestDeadlyPlotResolve:
    def test_mode0_destroys_creature(self):
        game = _make_game()
        alice = game.players[0]
        bob = game.players[1]
        creature = _make_creature("Foe", 3, 3)
        _place_on_battlefield(game, bob, creature)

        spell = DeadlyPlot()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.chosen_targets = [creature]
        spell.on_resolve(game)

        assert not game.get_battlefield(bob).contains(creature)

    def test_mode1_reanimates_zombie_from_graveyard(self):
        game = _make_game()
        alice = game.players[0]
        zombie = _make_creature("Zombie", 2, 2, subtypes={"Zombie"})
        _put_in_graveyard(game, alice, zombie)

        spell = DeadlyPlot()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.chosen_targets = [zombie]
        spell.on_resolve(game)

        assert game.get_battlefield(alice).contains(zombie)
        assert zombie.is_tapped is True


class TestSlagstormResolve:
    def test_mode0_damages_all_creatures(self):
        """Mode 0: 3 damage to each creature."""
        game = _make_game()
        alice, bob = game.players
        a_creature = _make_creature("Elf", 1, 4)
        b_creature = _make_creature("Orc", 3, 4)
        _place_on_battlefield(game, alice, a_creature)
        _place_on_battlefield(game, bob, b_creature)

        spell = Slagstorm()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.on_resolve(game)

        assert a_creature.damage_marked == 3
        assert b_creature.damage_marked == 3

    def test_mode1_damages_all_players(self):
        """Mode 1: 3 damage to each player."""
        game = _make_game()
        alice, bob = game.players

        spell = Slagstorm()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.on_resolve(game)

        assert alice.life == 17
        assert bob.life == 17


class TestSeekersFollyResolve:
    def test_mode0_opponent_discards_two(self):
        game = _make_game()
        alice, bob = game.players
        for i in range(3):
            _put_in_hand(game, bob, _make_creature(f"Card{i}"))

        spell = SeekersFolly()
        spell.controller = alice
        spell.chosen_mode = 0
        spell.chosen_targets = [bob]
        spell.on_resolve(game)

        assert len(game.get_hand(bob).get_all()) == 1

    def test_mode1_shrinks_opponent_creatures(self):
        game = _make_game()
        alice, bob = game.players
        orc = _make_creature("Orc", 3, 3)
        _place_on_battlefield(game, bob, orc)

        spell = SeekersFolly()
        spell.controller = alice
        spell.chosen_mode = 1
        spell.on_resolve(game)

        assert orc.base_power == 2
        assert orc.base_toughness == 2


# ===========================================================================
# MODAL CREATURE BEHAVIOUR TESTS
# ===========================================================================


class TestApothecaryStomperETB:
    def test_mode0_adds_counters_to_self(self):
        """Mode 0 with no target defaults to self — +2 counters."""
        game = _make_game()
        alice = game.players[0]
        stomper = ApothecaryStomper()
        stomper.controller = alice
        stomper.owner = alice
        stomper.chosen_mode = 0
        # No chosen_targets → defaults to self
        _place_on_battlefield(game, alice, stomper)
        stomper.register_triggers(game)
        _fire_etb_and_resolve(game, stomper)

        assert stomper.plus_one_counters == 2

    def test_mode1_gains_4_life(self):
        game = _make_game()
        alice = game.players[0]
        stomper = ApothecaryStomper()
        stomper.controller = alice
        stomper.owner = alice
        stomper.chosen_mode = 1
        _place_on_battlefield(game, alice, stomper)
        stomper.register_triggers(game)
        _fire_etb_and_resolve(game, stomper)

        assert alice.life == 24


class TestCharmingPrinceETB:
    def test_mode1_gains_3_life(self):
        game = _make_game()
        alice = game.players[0]
        prince = CharmingPrince()
        prince.controller = alice
        prince.owner = alice
        prince.chosen_mode = 1
        _place_on_battlefield(game, alice, prince)
        prince.register_triggers(game)
        _fire_etb_and_resolve(game, prince)

        assert alice.life == 23

    def test_mode2_exiles_target_creature(self):
        """Mode 2: exile another creature you own."""
        game = _make_game()
        alice = game.players[0]
        prince = CharmingPrince()
        prince.controller = alice
        prince.owner = alice
        other = _make_creature("Knight", 3, 3)
        _place_on_battlefield(game, alice, other)
        _place_on_battlefield(game, alice, prince)

        prince.chosen_mode = 2
        prince.chosen_targets = [other]
        prince.register_triggers(game)
        _fire_etb_and_resolve(game, prince)

        assert not game.get_battlefield(alice).contains(other)


# ===========================================================================
# X-COST SPELL BEHAVIOUR TESTS
# ===========================================================================


class TestExsanguinateResolve:
    def test_x_equals_5_drains_opponent(self):
        game = _make_game()
        alice, bob = game.players

        spell = Exsanguinate()
        spell.controller = alice
        spell.x_value = 5
        spell.on_resolve(game)

        assert bob.life == 15
        assert alice.life == 25

    def test_x_equals_0_does_nothing(self):
        """X=0 edge case: no life change."""
        game = _make_game()
        alice, bob = game.players

        spell = Exsanguinate()
        spell.controller = alice
        spell.x_value = 0
        spell.on_resolve(game)

        assert bob.life == 20
        assert alice.life == 20

    def test_scales_with_x(self):
        """Verify drain amount scales linearly with X."""
        game = _make_game()
        alice, bob = game.players

        spell = Exsanguinate()
        spell.controller = alice
        spell.x_value = 3
        spell.on_resolve(game)

        assert bob.life == 17
        assert alice.life == 23


class TestPrimalMightResolve:
    def test_pumps_creature_by_x(self):
        game = _make_game()
        alice = game.players[0]
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, alice, bear)

        spell = PrimalMight()
        spell.controller = alice
        spell.x_value = 3
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.base_power == 5
        assert bear.base_toughness == 5

    def test_pump_and_fight(self):
        """With two targets, pump first creature then fight."""
        game = _make_game()
        alice, bob = game.players
        attacker = _make_creature("Wolf", 2, 2)
        defender = _make_creature("Goblin", 1, 1)
        _place_on_battlefield(game, alice, attacker)
        _place_on_battlefield(game, bob, defender)

        spell = PrimalMight()
        spell.controller = alice
        spell.x_value = 2
        spell.chosen_targets = [attacker, defender]
        spell.on_resolve(game)

        # Wolf is now 4/4 after +2/+2
        assert attacker.base_power == 4
        # Goblin takes 4 damage from the 4-power wolf
        assert defender.damage_marked == 4

    def test_x_equals_0_no_pump(self):
        game = _make_game()
        alice = game.players[0]
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, alice, bear)

        spell = PrimalMight()
        spell.controller = alice
        spell.x_value = 0
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.base_power == 2
        assert bear.base_toughness == 2


class TestFinaleOfRevelationResolve:
    def test_draws_x_cards(self):
        game = _make_game()
        alice = game.players[0]
        for i in range(5):
            _put_in_library(alice, _make_creature(f"Card{i}"))

        spell = FinaleOfRevelation()
        spell.controller = alice
        spell.x_value = 3
        spell.on_resolve(game)

        assert len(game.get_hand(alice).get_all()) == 3

    def test_x_equals_0_draws_nothing(self):
        game = _make_game()
        alice = game.players[0]

        spell = FinaleOfRevelation()
        spell.controller = alice
        spell.x_value = 0
        spell.on_resolve(game)

        assert len(game.get_hand(alice).get_all()) == 0

    def test_x_gte_10_shuffles_graveyard_into_library(self):
        """X >= 10: graveyard cards should move to library before drawing."""
        game = _make_game()
        alice = game.players[0]
        # Put cards in graveyard
        gy_cards = [_make_creature(f"GY{i}") for i in range(3)]
        for c in gy_cards:
            _put_in_graveyard(game, alice, c)
        # Put enough cards in library to draw 10
        for i in range(10):
            _put_in_library(alice, _make_creature(f"Lib{i}"))

        spell = FinaleOfRevelation()
        spell.controller = alice
        spell.x_value = 10
        spell.on_resolve(game)

        # Graveyard should be empty (shuffled into library)
        assert len(alice.zones[Zone.GRAVEYARD].get_all()) == 0
        # Should have drawn 10 cards
        assert len(game.get_hand(alice).get_all()) == 10


# ===========================================================================
# KICKER SPELL BEHAVIOUR TESTS
# ===========================================================================


class TestBurstLightningResolve:
    def test_unkicked_deals_2_damage(self):
        game = _make_game()
        alice, bob = game.players

        spell = BurstLightning()
        spell.controller = alice
        spell.kicked = False
        spell.chosen_targets = [bob]
        spell.on_resolve(game)

        assert bob.life == 18

    def test_kicked_deals_4_damage(self):
        game = _make_game()
        alice, bob = game.players

        spell = BurstLightning()
        spell.controller = alice
        spell.kicked = True
        spell.chosen_targets = [bob]
        spell.on_resolve(game)

        assert bob.life == 16


class TestIntoTheRoilResolve:
    def test_unkicked_bounces_only(self):
        game = _make_game()
        alice, bob = game.players
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, bob, bear)

        spell = IntoTheRoil()
        spell.controller = alice
        spell.kicked = False
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert not game.get_battlefield(bob).contains(bear)
        assert game.get_hand(bob).contains(bear)
        # Should NOT draw a card when not kicked
        assert len(game.get_hand(alice).get_all()) == 0

    def test_kicked_bounces_and_draws(self):
        game = _make_game()
        alice, bob = game.players
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, bob, bear)
        _put_in_library(alice, _make_creature("Card"))

        spell = IntoTheRoil()
        spell.controller = alice
        spell.kicked = True
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert not game.get_battlefield(bob).contains(bear)
        assert len(game.get_hand(alice).get_all()) == 1


class TestGnarlidColonyETB:
    def test_unkicked_no_counters(self):
        game = _make_game()
        alice = game.players[0]
        colony = GnarlidColony()
        colony.controller = alice
        colony.owner = alice
        colony.kicked = False
        _place_on_battlefield(game, alice, colony)
        colony.register_triggers(game)
        _fire_etb_and_resolve(game, colony)

        assert colony.plus_one_counters == 0

    def test_kicked_enters_with_two_counters(self):
        game = _make_game()
        alice = game.players[0]
        colony = GnarlidColony()
        colony.controller = alice
        colony.owner = alice
        colony.kicked = True
        _place_on_battlefield(game, alice, colony)
        colony.register_triggers(game)
        _fire_etb_and_resolve(game, colony)

        assert colony.plus_one_counters == 2


class TestGatekeeperOfMalakirETB:
    def test_unkicked_no_sacrifice(self):
        """Not kicked: no sacrifice trigger."""
        game = _make_game()
        alice, bob = game.players
        gatekeeper = GatekeeperOfMalakir()
        gatekeeper.controller = alice
        gatekeeper.owner = alice
        gatekeeper.kicked = False
        victim = _make_creature("Victim", 1, 1)
        _place_on_battlefield(game, bob, victim)
        _place_on_battlefield(game, alice, gatekeeper)
        gatekeeper.register_triggers(game)
        _fire_etb_and_resolve(game, gatekeeper)

        # Victim should still be on battlefield
        assert game.get_battlefield(bob).contains(victim)

    def test_kicked_forces_sacrifice(self):
        """Kicked: target player sacrifices a creature."""
        game = _make_game()
        alice, bob = game.players
        gatekeeper = GatekeeperOfMalakir()
        gatekeeper.controller = alice
        gatekeeper.owner = alice
        gatekeeper.kicked = True
        victim = _make_creature("Victim", 1, 1)
        _place_on_battlefield(game, bob, victim)
        _place_on_battlefield(game, alice, gatekeeper)
        gatekeeper.chosen_targets = [bob]
        gatekeeper.register_triggers(game)
        _fire_etb_and_resolve(game, gatekeeper)

        assert not game.get_battlefield(bob).contains(victim)


# ===========================================================================
# REGISTRATION
# ===========================================================================


class TestRegistration:
    def test_register_complex_spells_count(self):
        registry = CardRegistry()
        register_complex_spells(registry)
        assert len(registry) == 16

    def test_all_names_registered(self):
        registry = CardRegistry()
        register_complex_spells(registry)
        expected = {
            "Abrade", "Valorous Stance", "Goblin Surprise", "Deadly Plot",
            "Slagstorm", "Bushwhack", "Seeker's Folly",
            "Apothecary Stomper", "Charming Prince",
            "Exsanguinate", "Primal Might", "Finale of Revelation",
            "Burst Lightning", "Into the Roil",
            "Gnarlid Colony", "Gatekeeper of Malakir",
        }
        assert set(registry.list_all()) == expected

    def test_registry_creates_correct_instances(self):
        """Spot-check that registry creates the right class."""
        registry = CardRegistry()
        register_complex_spells(registry)
        card = registry.create_instance("Abrade")
        assert isinstance(card, Abrade)
        assert card.name == "Abrade"
