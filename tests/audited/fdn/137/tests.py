"""Audited tests for Authority of the Consuls (FDN collector number 137)."""
from __future__ import annotations
import pytest
from card_impl import AuthorityOfTheConsuls
from engine.card import Enchantment, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAuthorityOfTheConsulsBasic:
    def test_is_enchantment(self) -> None:
        card = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_name(self) -> None:
        card = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=None)
        assert card.name == "Authority of the Consuls"
    def test_not_aura(self) -> None:
        card = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=None)
        assert not card.is_aura

@pytest.mark.ability
class TestAuthorityOfTheConsulsAbility:
    def test_opponents_creatures_enter_tapped(self) -> None:
        """Opponents' summoning-sick creatures should be tapped via static effect."""
        game = create_game()
        auth = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=game.players[0])
        auth.controller = game.players[0]
        set_board_state(game, 0, battlefield=[auth])
        auth.on_resolve(game)
        # Simulate opponent creature entering with summoning sickness
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[1])
        opp_creature.controller = game.players[1]
        opp_creature.summoning_sick = True
        set_board_state(game, 1, battlefield=[opp_creature])
        game.effect_manager.apply_all(game)
        assert opp_creature.is_tapped, "Opponent's creature should enter tapped"

    def test_own_creatures_not_affected(self) -> None:
        """Controller's own creatures should NOT be tapped by Authority."""
        game = create_game()
        auth = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=game.players[0])
        auth.controller = game.players[0]
        set_board_state(game, 0, battlefield=[auth])
        auth.on_resolve(game)
        own_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        own_creature.controller = game.players[0]
        own_creature.summoning_sick = True
        bf = game.get_battlefield(game.players[0])
        bf.add(own_creature)
        game.effect_manager.apply_all(game)
        assert not own_creature.is_tapped, "Own creature should NOT be tapped"

@pytest.mark.edge
class TestAuthorityOfTheConsulsEdge:
    def test_effect_stops_when_enchantment_leaves_battlefield(self) -> None:
        """Once Authority leaves the battlefield, its static effect should stop."""
        from engine.game import destroy
        game = create_game()
        auth = AuthorityOfTheConsuls(name="Authority of the Consuls", owner=game.players[0])
        auth.controller = game.players[0]
        set_board_state(game, 0, battlefield=[auth])
        auth.on_resolve(game)
        # Destroy the enchantment
        destroy(game, auth)
        # Now an opponent creature entering should NOT be tapped
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[1])
        opp_creature.controller = game.players[1]
        opp_creature.summoning_sick = True
        set_board_state(game, 1, battlefield=[opp_creature])
        game.effect_manager.apply_all(game)
        assert not opp_creature.is_tapped, "Effect should stop once enchantment leaves"
