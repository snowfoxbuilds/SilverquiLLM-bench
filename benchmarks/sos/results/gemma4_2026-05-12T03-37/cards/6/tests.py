import pytest
from test_utils import create_game, set_board_state, cast_spell
from engine.types import ManaType, CardType, ManaCost
from engine.card import Creature
from card_impl import AjanisResponse

class MockCreature(Creature):
    def __init__(self, **kwargs):
        # Use kwargs name if provided, otherwise default to "TestCreature"
        name = kwargs.pop("name", "TestCreature")
        super().__init__(
            name=name,
            mana_cost=ManaCost.parse("{1}"),
            card_types={CardType.CREATURE},
            base_power=1,
            base_toughness=1,
            **kwargs
        )

class TestAjanisResponse:
    def test_basic_stats(self):
        card = AjanisResponse()
        assert card.name == "Ajani's Response"
        assert card.mana_cost.generic == 4
        assert card.mana_cost.pips[ManaType.WHITE] == 1
        assert CardType.INSTANT in card.card_types

    def test_cast_untapped_full_cost(self):
        game = create_game()
        creature = MockCreature()
        creature.is_tapped = False
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[creature])
        
        # We need to ensure the engine picks the right target for the cost reduction check.
        # cast_spell helper usually handles targeting.
        cast_spell(game, 0, "Ajani's Response", targets=[creature])
        
        # Check if it was destroyed
        assert not game.get_battlefield(game.players[1]).contains(creature)
        # Check mana spent: 4 generic + 1 white = 5. 
        # (Wait, set_board_state sets the initial pool. I can't easily check final pool 
        # unless I know the engine's mana_pool.pay implementation. 
        # But if it cast successfully with 5, it's a good sign.)

    def test_cast_tapped_reduced_cost(self):
        game = create_game()
        creature = MockCreature()
        creature.is_tapped = True
        # Only 2 white mana (should be enough for {1}{W})
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 2})
        set_board_state(game, 1, battlefield=[creature])
        
        cast_spell(game, 0, "Ajani's Response", targets=[creature])
        
        assert not game.get_battlefield(game.players[1]).contains(creature)

    def test_cast_tapped_insufficient_mana_for_full_cost(self):
        game = create_game()
        creature = MockCreature()
        creature.is_tapped = False # Untapped, needs {4}{W}
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 2})
        set_board_state(game, 1, battlefield=[creature])
        
        with pytest.raises(Exception): # CastingError
            cast_spell(game, 0, "Ajani's Response", targets=[creature])

    def test_destroy_target(self):
        game = create_game()
        creature = MockCreature()
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[creature])
        
        cast_spell(game, 0, "Ajani's Response", targets=[creature])
        assert not game.get_battlefield(game.players[1]).contains(creature)
        assert game.get_graveyard(game.players[1]).contains(creature)

    def test_fizzle_if_target_gone(self):
        game = create_game()
        creature = MockCreature()
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[creature])
        
        # Manually put on stack and remove target
        card = AjanisResponse()
        # We can't easily use cast_spell and then modify state before resolution 
        # because cast_spell resolves immediately.
        # I'll have to use the engine directly or a mock.
        # However, I can test the on_resolve logic by manually calling it.
        
        card.chosen_targets = [creature]
        # Remove creature from battlefield
        game.get_battlefield(game.players[1]).remove(creature)
        
        card.on_resolve(game)
        # Should not crash and not destroy anything else
        assert not game.get_battlefield(game.players[1]).contains(creature)

    def test_no_valid_targets(self):
        game = create_game()
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[]) # No creatures
        
        # get_targets should return an empty list or the cast should fail
        # In this engine, if get_targets returns [TargetRequirement], 
        # but no objects match, the choice will fail.
        with pytest.raises(Exception):
            cast_spell(game, 0, "Ajani's Response")

    def test_targets_multiple_creatures(self):
        game = create_game()
        c1 = MockCreature(name="C1")
        c2 = MockCreature(name="C2")
        set_board_state(game, 0, hand=[AjanisResponse()], mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[c1, c2])
        
        cast_spell(game, 0, "Ajani's Response", targets=[c1])
        assert not game.get_battlefield(game.players[1]).contains(c1)
        assert game.get_battlefield(game.players[1]).contains(c2)
