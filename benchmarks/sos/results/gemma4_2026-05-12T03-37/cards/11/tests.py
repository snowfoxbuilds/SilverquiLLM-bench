import pytest
from test_utils import create_game, set_board_state, cast_spell
from card_impl import EagerGlyphmage
from engine.types import ManaType, Color, Keyword, CardType
from engine.protection import get_colors

class TestEagerGlyphmage:
    def test_basic_stats(self):
        card = EagerGlyphmage()
        assert card.name == "Eager Glyphmage"
        assert card.mana_cost.generic == 3
        assert card.mana_cost.pips[ManaType.WHITE] == 1
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert CardType.CREATURE in card.card_types
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_etb_creates_token(self):
        game = create_game()
        set_board_state(game, 0, hand=[EagerGlyphmage()], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 3})
        
        cast_spell(game, 0, "Eager Glyphmage")
        
        # Check if Eager Glyphmage is on battlefield
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "Eager Glyphmage" for c in bf.get_all())
        
        # Check if Inkling token was created
        tokens = [c for c in bf.get_all() if c.name == "Inkling"]
        assert len(tokens) == 1
        
        inkling = tokens[0]
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1
        assert inkling.keywords & Keyword.FLYING
        assert get_colors(inkling) == {Color.WHITE, Color.BLACK}
        assert inkling.is_token is True

    def test_etb_controller(self):
        game = create_game()
        # Player 1 casts Eager Glyphmage
        set_board_state(game, 1, hand=[EagerGlyphmage()], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 3})
        cast_spell(game, 1, "Eager Glyphmage")
        
        bf1 = game.get_battlefield(game.players[1])
        tokens = [c for c in bf1.get_all() if c.name == "Inkling"]
        assert len(tokens) == 1
        assert tokens[0].controller == game.players[1]

    def test_multiple_etbs(self):
        game = create_game()
        set_board_state(game, 0, hand=[EagerGlyphmage(), EagerGlyphmage()], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 6})
        
        cast_spell(game, 0, "Eager Glyphmage")
        cast_spell(game, 0, "Eager Glyphmage")
        
        bf = game.get_battlefield(game.players[0])
        tokens = [c for c in bf.get_all() if c.name == "Inkling"]
        assert len(tokens) == 2

    def test_no_mana_no_token(self):
        game = create_game()
        set_board_state(game, 0, hand=[EagerGlyphmage()], mana={})
        
        # This should fail or not resolve
        with pytest.raises(Exception):
            cast_spell(game, 0, "Eager Glyphmage")
            
        bf = game.get_battlefield(game.players[0])
        assert not any(c.name == "Inkling" for c in bf.get_all())
