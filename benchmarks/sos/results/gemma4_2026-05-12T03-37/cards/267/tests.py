import pytest
from test_utils import create_game, set_board_state
from card_impl import Plains
from engine.types import ManaType, CardType, Supertype
from engine.abilities import activate_ability, ActivatedAbilityInstance, AbilityError
from engine.card import ManaAbility

def get_mana_ability_instance(game, card):
    """Helper to convert a ManaAbility to an ActivatedAbilityInstance."""
    mana_ability = card.get_mana_abilities()[0]
    return ActivatedAbilityInstance(
        source=card,
        controller=card.controller,
        cost=mana_ability.cost,
        effect=mana_ability.mana_produced,
        is_mana_ability=True,
        description=mana_ability.description
    )

class TestPlains:
    def test_basic_attributes(self):
        plains = Plains()
        assert plains.name == "Plains"
        assert plains.mana_cost.cmc == 0
        assert CardType.LAND in plains.card_types
        assert Supertype.BASIC in plains.supertypes
        assert "Plains" in plains.subtypes
        assert plains.rules_text == "({T}: Add {W}.)"

    def test_mana_ability_success(self):
        game = create_game()
        plains = Plains()
        set_board_state(game, 0, battlefield=[plains])
        
        instance = get_mana_ability_instance(game, plains)
        activate_ability(game, game.players[0], instance)
        
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1
        assert plains.is_tapped is True

    def test_mana_ability_failure_tapped(self):
        game = create_game()
        plains = Plains()
        plains.is_tapped = True
        set_board_state(game, 0, battlefield=[plains])
        
        instance = get_mana_ability_instance(game, plains)
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, game.players[0], instance)
            
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 0

    def test_mana_ability_correct_player(self):
        game = create_game()
        plains = Plains()
        # Player 0 controls the land
        set_board_state(game, 0, battlefield=[plains])
        
        instance = get_mana_ability_instance(game, plains)
        # Player 0 activates the ability
        activate_ability(game, game.players[0], instance)
        
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1
        assert game.players[1].mana_pool.get(ManaType.WHITE) == 0

    def test_multiple_plains(self):
        game = create_game()
        p1 = Plains()
        p2 = Plains()
        set_board_state(game, 0, battlefield=[p1, p2])
        
        inst1 = get_mana_ability_instance(game, p1)
        inst2 = get_mana_ability_instance(game, p2)
        
        activate_ability(game, game.players[0], inst1)
        activate_ability(game, game.players[0], inst2)
        
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 2
        assert p1.is_tapped is True
        assert p2.is_tapped is True

    def test_untap_and_reactivate(self):
        game = create_game()
        plains = Plains()
        set_board_state(game, 0, battlefield=[plains])
        
        instance = get_mana_ability_instance(game, plains)
        
        # First activation
        activate_ability(game, game.players[0], instance)
        assert plains.is_tapped is True
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1
        
        # Untap
        plains.is_tapped = False
        
        # Second activation
        activate_ability(game, game.players[0], instance)
        assert plains.is_tapped is True
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 2
