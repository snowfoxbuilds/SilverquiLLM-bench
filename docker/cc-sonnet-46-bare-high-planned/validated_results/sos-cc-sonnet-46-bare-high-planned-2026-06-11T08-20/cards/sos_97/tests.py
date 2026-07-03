"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

import random
import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack


def _sorcery_speed(game, idx=0):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = idx


def _activate_ability(game, player, pw, ability_index):
    """Helper: activate a loyalty ability and resolve it."""
    abilities = pw.get_loyalty_abilities()
    ab = abilities[ability_index]
    instance = LoyaltyAbilityInstance(
        source=pw,
        controller=player,
        loyalty_cost=ab.loyalty_cost,
        effect=ab.effect,
    )
    activate_ability(game, player, instance)
    _resolve_top_of_stack(game)


class TestRalZarekGuestLecturer:
    def test_starting_loyalty(self):
        """Starts at 3 loyalty."""
        ral = RalZarekGuestLecturer()
        assert ral.loyalty == 3

    def test_surveil_puts_cards_in_graveyard(self):
        """Surveil 2: cards chosen for graveyard end up in graveyard."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.register_triggers(game)
        ral.loyalty = 3
        _sorcery_speed(game)

        # Fill library: top=card2, below=card1
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=2, base_toughness=2)
        c1.owner = p1
        c2.owner = p1
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)  # c2 on top

        # Surveil: put both in graveyard
        p1._script.appendleft(True)  # c2 → graveyard
        p1._script.appendleft(True)  # c1 → graveyard

        _activate_ability(game, p1, ral, 0)

        assert c1 in p1.zones[Zone.GRAVEYARD].get_all()
        assert c2 in p1.zones[Zone.GRAVEYARD].get_all()
        assert ral.loyalty == 4  # +1

    def test_surveil_keeps_cards_on_top(self):
        """Surveil 2: cards not sent to graveyard stay on top of library."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.register_triggers(game)
        ral.loyalty = 3
        _sorcery_speed(game)

        c1 = Creature(name="Keep1", base_power=1, base_toughness=1)
        c2 = Creature(name="Keep2", base_power=2, base_toughness=2)
        c1.owner = p1
        c2.owner = p1
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)

        # Keep both
        p1._script.appendleft(False)  # c2 → keep
        p1._script.appendleft(False)  # c1 → keep

        _activate_ability(game, p1, ral, 0)

        lib = p1.zones[Zone.LIBRARY].get_all()
        assert c1 in lib
        assert c2 in lib

    def test_minus1_discard(self):
        """−1: Targeted players discard."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.loyalty = 3
        _sorcery_speed(game)

        discard_card = Creature(name="Discard", base_power=1, base_toughness=1)
        discard_card.owner = p2
        set_board_state(game, 1, hand=[discard_card])

        # Set target
        ral._resolve_targets = [p2]
        p2._script.appendleft(discard_card)

        abilities = ral.get_loyalty_abilities()
        ab = abilities[1]  # −1
        instance = LoyaltyAbilityInstance(
            source=ral, controller=p1, loyalty_cost=ab.loyalty_cost, effect=ab.effect
        )
        activate_ability(game, p1, instance)
        _resolve_top_of_stack(game)

        assert discard_card in p2.zones[Zone.GRAVEYARD].get_all()
        assert ral.loyalty == 2  # 3 - 1

    def test_minus2_reanimates(self):
        """−2: Return target creature from graveyard to battlefield."""
        from engine.zones import move_to_zone
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.loyalty = 5
        _sorcery_speed(game)

        # Put a 2/2 creature (MV 2) in graveyard
        bear = Creature(name="ReanimBear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        bear.owner = p1
        bear.controller = p1
        p1.zones[Zone.GRAVEYARD].add(bear)

        ral._resolve_target = bear

        _activate_ability(game, p1, ral, 2)  # −2

        assert game.get_battlefield(p1).contains(bear)
        assert ral.loyalty == 3  # 5 - 2

    def test_minus7_skip_turns_all_heads(self):
        """−7: All 5 coins heads → target opponent skips 5 turns."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.loyalty = 10
        _sorcery_speed(game)

        # Seed RNG to always get heads (1)
        game.rng = random.Random()
        game.rng.seed(42)  # seed for determinism

        ral._resolve_target = p2

        # Force all heads by monkeypatching
        game.rng.randint = lambda a, b: 1  # always heads

        _activate_ability(game, p1, ral, 3)  # −7

        assert p2.skip_turns == 5
        assert ral.loyalty == 3  # 10 - 7

    def test_minus7_skip_turns_all_tails(self):
        """−7: All tails → 0 turns skipped."""
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        ral.controller = p1
        ral.loyalty = 10
        _sorcery_speed(game)

        game.rng = random.Random()
        game.rng.randint = lambda a, b: 0  # always tails

        ral._resolve_target = p2

        _activate_ability(game, p1, ral, 3)  # −7

        assert getattr(p2, "skip_turns", 0) == 0
        assert ral.loyalty == 3

    def test_skip_turns_advance_phase(self):
        """skip_turns decrements and the active player changes when skipping."""
        game = create_game()
        p1, p2 = game.players
        p2.skip_turns = 1

        # Set up at end of turn for p1 (so next player would be p2)
        game.active_player_index = 0
        game._normal_next_index = 1

        # Force the turn to end (advance through CLEANUP phase)
        from engine.types import Phase, Step
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        # p2 should be skipped → p1 gets the turn again
        # (skip_turns decremented from 1 to 0)
        assert game.active_player_index == 0
        assert p2.skip_turns == 0
