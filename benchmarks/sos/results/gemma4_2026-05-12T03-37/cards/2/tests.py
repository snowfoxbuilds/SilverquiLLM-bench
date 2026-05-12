import pytest
from test_utils import create_game, set_board_state, cast_spell
from card_impl import RancorousArchaic
from engine.types import ManaType, Keyword

class TestRancorousArchaic:
    def test_basic_stats(self):
        card = RancorousArchaic()
        assert card.name == "Rancorous Archaic"
        assert card.mana_cost.generic == 5
        assert card.base_power == 2
        assert card.base_toughness == 2
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.REACH in card.keywords

    def test_converge_zero_colors(self):
        game = create_game()
        # Pay {5} using COLORLESS mana
        set_board_state(game, 0, hand=[RancorousArchaic()], mana={ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Rancorous Archaic")
        
        creature = game.get_battlefield(game.players[0]).get_all()[0]
        assert creature.counters.get("+1/+1", 0) == 0
        assert creature.power == 2
        assert creature.toughness == 2

    def test_converge_one_color(self):
        game = create_game()
        # Pay {5} using only WHITE mana
        set_board_state(game, 0, hand=[RancorousArchaic()], mana={ManaType.WHITE: 5})
        cast_spell(game, 0, "Rancorous Archaic")
        
        creature = game.get_battlefield(game.players[0]).get_all()[0]
        assert creature.counters.get("+1/+1", 0) == 1
        assert creature.power == 3
        assert creature.toughness == 3

    def test_converge_five_colors(self):
        game = create_game()
        # Pay {5} using 5 different colors
        set_board_state(game, 0, hand=[RancorousArchaic()], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.RED: 1,
            ManaType.GREEN: 1,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        
        creature = game.get_battlefield(game.players[0]).get_all()[0]
        assert creature.counters.get("+1/+1", 0) == 5
        assert creature.power == 7
        assert creature.toughness == 7

    def test_converge_mixed_colors(self):
        game = create_game()
        # Pay {5} using 3 colors (e.g., 2W, 2U, 1B)
        set_board_state(game, 0, hand=[RancorousArchaic()], mana={
            ManaType.WHITE: 2,
            ManaType.BLUE: 2,
            ManaType.BLACK: 1,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        
        creature = game.get_battlefield(game.players[0]).get_all()[0]
        assert creature.counters.get("+1/+1", 0) == 3
        assert creature.power == 5
        assert creature.toughness == 5

    def test_converge_with_colorless_and_colored(self):
        game = create_game()
        # Pay {5} using 2 colors and some colorless (e.g., 1W, 1U, 3 Colorless)
        set_board_state(game, 0, hand=[RancorousArchaic()], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.COLORLESS: 3,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        
        creature = game.get_battlefield(game.players[0]).get_all()[0]
        assert creature.counters.get("+1/+1", 0) == 2
        assert creature.power == 4
        assert creature.toughness == 4
