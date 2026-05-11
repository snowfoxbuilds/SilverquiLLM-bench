"""Audited tests for Ajani, Caller of the Pride (FDN — synthetic dir 818)."""
from __future__ import annotations
import pytest
from card_impl import AjaniCallerOfThePride
from engine.card import Planeswalker, Creature
from engine.types import CardType, Supertype, Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAjaniBasic:
    def test_is_planeswalker(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
    def test_is_legendary(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert Supertype.LEGENDARY in card.supertypes
    def test_starting_loyalty_is_4(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert card.loyalty == 4
        assert card.starting_loyalty == 4
    def test_has_ajani_subtype(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert "Ajani" in card.subtypes

@pytest.mark.ability
class TestAjaniAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 3
    def test_plus_one_cost(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert card.get_loyalty_abilities()[0].loyalty_cost == +1
    def test_minus_three_cost(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert card.get_loyalty_abilities()[1].loyalty_cost == -3
    def test_minus_eight_cost(self) -> None:
        card = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=None)
        assert card.get_loyalty_abilities()[2].loyalty_cost == -8
    def test_plus1_puts_counter_on_creature(self) -> None:
        """Ajani's +1 should put a +1/+1 counter on target creature."""
        game = create_game()
        pw = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw.controller = game.players[0]
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[pw, c])
        pw._resolve_target = c
        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)
        assert c.plus_one_counters >= 1
    def test_minus3_grants_flying_and_double_strike(self) -> None:
        """Ajani's -3 grants flying and double strike."""
        game = create_game()
        pw = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw.controller = game.players[0]
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[pw, c])
        pw._resolve_target = c
        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DOUBLE_STRIKE in c.keywords

@pytest.mark.rules
class TestAjaniLoyaltyPipeline:
    def test_loyalty_activation_adjusts_loyalty_up(self) -> None:
        """Activating +1 ability through pipeline should increase loyalty to 5."""
        from engine.abilities import activate_ability, LoyaltyAbilityInstance, clear_loyalty_tracking
        from engine.types import Phase
        clear_loyalty_tracking()
        game = create_game()
        pw = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw.controller = game.players[0]
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[pw, c])
        pw._resolve_target = c
        # Set sorcery-speed conditions
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        loyalty_abilities = pw.get_loyalty_abilities()
        lai = LoyaltyAbilityInstance(
            source=pw,
            controller=game.players[0],
            loyalty_cost=loyalty_abilities[0].loyalty_cost,
            effect=loyalty_abilities[0].effect,
        )
        activate_ability(game, game.players[0], lai)
        assert pw.loyalty == 5  # was 4, +1 = 5

    def test_loyalty_activation_adjusts_loyalty_down(self) -> None:
        """Activating -3 ability through pipeline should decrease loyalty to 1."""
        from engine.abilities import activate_ability, LoyaltyAbilityInstance, clear_loyalty_tracking
        from engine.types import Phase
        clear_loyalty_tracking()
        game = create_game()
        pw = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw.controller = game.players[0]
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[pw, c])
        pw._resolve_target = c
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        loyalty_abilities = pw.get_loyalty_abilities()
        lai = LoyaltyAbilityInstance(
            source=pw,
            controller=game.players[0],
            loyalty_cost=loyalty_abilities[1].loyalty_cost,
            effect=loyalty_abilities[1].effect,
        )
        activate_ability(game, game.players[0], lai)
        assert pw.loyalty == 1  # was 4, -3 = 1

    def test_loyalty_cannot_activate_twice_per_turn(self) -> None:
        """Once-per-turn restriction: second activation should raise AbilityError."""
        from engine.abilities import activate_ability, LoyaltyAbilityInstance, AbilityError, clear_loyalty_tracking
        from engine.types import Phase
        clear_loyalty_tracking()
        game = create_game()
        pw = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw.controller = game.players[0]
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        set_board_state(game, 0, battlefield=[pw, c])
        pw._resolve_target = c
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        loyalty_abilities = pw.get_loyalty_abilities()
        lai = LoyaltyAbilityInstance(
            source=pw,
            controller=game.players[0],
            loyalty_cost=loyalty_abilities[0].loyalty_cost,
            effect=loyalty_abilities[0].effect,
        )
        activate_ability(game, game.players[0], lai)
        # Second activation should fail
        lai2 = LoyaltyAbilityInstance(
            source=pw,
            controller=game.players[0],
            loyalty_cost=loyalty_abilities[0].loyalty_cost,
            effect=loyalty_abilities[0].effect,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, game.players[0], lai2)

    def test_legend_rule_destroys_duplicate(self) -> None:
        """Two legendary planeswalkers with same name — legend rule moves one to graveyard."""
        from engine.state_based_actions import check_state_based_actions
        # Create game with script so player can choose which to keep
        game = create_game()
        pw1 = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw1.controller = game.players[0]
        pw2 = AjaniCallerOfThePride(name="Ajani, Caller of the Pride", owner=game.players[0])
        pw2.controller = game.players[0]
        set_board_state(game, 0, battlefield=[pw1, pw2])
        # Script the player to choose pw1 to keep
        game.players[0]._script.append(pw1)
        check_state_based_actions(game)
        bf = game.get_battlefield(game.players[0])
        bf_pws = [o for o in bf.get_all() if isinstance(o, Planeswalker) and o.name == "Ajani, Caller of the Pride"]
        assert len(bf_pws) == 1, "Legend rule should leave only one copy"
