import pytest
from test_utils import create_game, set_board_state, cast_spell
from card_impl import RalZarekGuestLecturer
from engine.types import ManaType, Zone, CardType, ManaCost
from engine.game import discard
from engine.zones import ZoneContainer
from collections import deque
import random

class TestRalZarekGuestLecturer:
    def test_basic_stats(self):
        card = RalZarekGuestLecturer()
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost.cmc == 3
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_loyalty_plus_one_surveil(self):
        game = create_game()
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral], mana={ManaType.BLACK: 2})
        
        # Add cards to library to ensure surveil has targets
        from engine.card import CardImpl
        for i in range(5):
            game.players[0].zones[Zone.LIBRARY].add(CardImpl(name=f"Card {i}"))
        
        # Mock choice: "bottom", then "graveyard"
        game.players[0]._script = deque(["bottom", "graveyard"])
        
        # Activate +1
        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)
        
        # Check that one card went to graveyard (since we chose "graveyard" for the second)
        assert len(game.players[0].zones[Zone.GRAVEYARD]) == 1

    def test_loyalty_minus_one_discard(self):
        game = create_game()
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        
        # Opponent has cards in hand
        opponent_card = RalZarekGuestLecturer()
        set_board_state(game, 1, hand=[opponent_card])
        
        # Mock choice: "all" targets, then opponent chooses card
        game.players[0]._script = deque(["all"])
        game.players[1]._script = deque([opponent_card])
        
        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)
        
        assert len(game.players[1].zones[Zone.HAND]) == 0
        assert len(game.players[1].zones[Zone.GRAVEYARD]) == 1

    def test_loyalty_minus_two_reanimate(self):
        game = create_game()
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        
        # Create a creature card
        from engine.card import Creature
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        
        # Mock choice: choose the bear
        game.players[0]._script = deque([bear])
        
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)
        
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(bear)
        assert not game.players[0].zones[Zone.GRAVEYARD].contains(bear)

    def test_loyalty_minus_seven_skip_turns(self):
        game = create_game()
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        
        # Mock coin flips: all heads (5)
        import unittest.mock as mock
        with mock.patch('random.random', return_value=0.1):
            ability = ral.get_loyalty_abilities()[3]
            ability.effect(game)
        
        assert game.players[1].turns_to_skip == 5

    def test_skip_turns_execution(self):
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]
        
        player1.turns_to_skip = 1
        
        # Current active is player 0. Advance to player 1's turn.
        while game.active_player_index == 0:
            game.advance_phase()
        
        # Run turn for player 1. It should be skipped.
        from engine.turn import run_turn
        run_turn(game)
        
        # Player 1 should have 0 skips now, and it should be player 0's turn again.
        assert player1.turns_to_skip == 0
        assert game.active_player_index == 0
