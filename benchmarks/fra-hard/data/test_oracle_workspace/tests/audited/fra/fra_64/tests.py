import pytest
from card_impl import SanctumLurker
from engine.abilities import AbilityError
from engine.card import Planeswalker
from engine.game import exile, remove_counter
from engine.types import CardType, Phase, Step, Zone
from test_utils import (
    activate_loyalty_ability,
    advance_game_to_phase,
    behavioral_game,
    enter_permanent,
    put_on_battlefield,
    resolve_stack,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    lurker = enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    jace = next(c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes)
    return game, player, lurker, jace


def test_enters_creates_jace_with_one_loyalty():
    _game, _player, lurker, jace = arrange()
    assert jace.is_token and jace.loyalty == 1
    assert CardType.PLANESWALKER in jace.card_types
    assert lurker.power == 3 and lurker.toughness == 2


def test_second_empower_reuses_token():
    game, player, _, jace = arrange()
    enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    assert jace.loyalty == 2
    assert len([c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes]) == 1


def test_granted_plus_two_drains_and_gains():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    assert jace.loyalty == 3 and game.players[1].life == 20
    resolve_stack(game)
    assert player.life == 21 and game.players[1].life == 19


def test_granted_ability_obeys_once_per_turn():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    resolve_stack(game)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, jace, 0)
    assert jace.loyalty == 3


def test_granted_ability_obeys_sorcery_timing():
    game, player, _, jace = arrange()
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, jace, 2)
    assert jace.loyalty == 1


def test_zero_loyalty_token_survives_minus_one():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 0)
    resolve_stack(game)
    assert jace.loyalty == 0 and game.get_battlefield(player).contains(jace)
    assert len(player.zones[Zone.GRAVEYARD].get_all()) == 1


def test_zero_loyalty_dies_when_lurker_leaves():
    game, player, lurker, jace = arrange()
    remove_counter(game, jace, "loyalty", 1)
    exile(game, lurker)
    resolve_stack(game)
    assert not game.get_battlefield(player).contains(jace)


def test_second_lurker_keeps_zero_loyalty_safe():
    game, player, lurker, jace = arrange()
    other = enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    remove_counter(game, jace, "loyalty", 2)
    exile(game, lurker)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(jace)
    exile(game, other)
    resolve_stack(game)
    assert not game.get_battlefield(player).contains(jace)


def test_nontoken_planeswalker_also_gets_protection_and_ability():
    game, player, _, _ = arrange()
    walker = enter_permanent(game, player, Planeswalker(name="Visitor", starting_loyalty=0))
    resolve_stack(game)
    activate_loyalty_ability(game, player, walker)
    resolve_stack(game)
    assert walker.loyalty == 2 and player.life == 21


def test_opponents_planeswalker_not_protected():
    game, _player, _, _ = arrange()
    opponent = game.players[1]
    walker = put_on_battlefield(game, opponent, Planeswalker(name="Opposing walker", starting_loyalty=0))
    resolve_stack(game)
    assert opponent.zones[Zone.GRAVEYARD].contains(walker)


def test_existing_nontoken_jace_does_not_replace_token_creation():
    game = behavioral_game()
    player = game.players[0]
    walker = enter_permanent(game, player, Planeswalker(name="Jace visitor", subtypes={"Jace"}, starting_loyalty=4))
    enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    assert walker.loyalty == 4
    assert len([c for c in game.get_battlefield(player).get_all() if CardType.PLANESWALKER in c.card_types]) == 2


def test_grant_disappears_but_pending_ability_resolves():
    game, player, lurker, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    exile(game, lurker)
    resolve_stack(game)
    assert player.life == 21
    with pytest.raises(IndexError):
        activate_loyalty_ability(game, player, jace, 2)
