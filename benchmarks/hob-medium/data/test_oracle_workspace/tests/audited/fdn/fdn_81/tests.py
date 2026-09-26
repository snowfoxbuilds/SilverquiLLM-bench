"""Chandra's +2 uses canonical loyalty activation; -4 baseline gaps are recorded separately."""

import pytest
from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
from engine.abilities import AbilityError
from engine.card import Creature, Planeswalker
from engine.decisions import GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase
from test_utils import (
    activate_loyalty_ability,
    behavioral_game,
    create_game,
    enter_permanent,
    resolve_stack,
)


def test_is_planeswalker():
    assert isinstance(ChandraFlameshaper(), Planeswalker)


def test_name():
    assert ChandraFlameshaper().name == "Chandra, Flameshaper"


def test_mana_cost():
    assert ChandraFlameshaper().mana_cost == ManaCost.parse("{5}{R}{R}")


def test_plus_two_adds_mana_and_exiles_three_cards():
    game = behavioral_game()
    player = game.players[0]
    card = enter_permanent(game, player, ChandraFlameshaper())
    before = len(game.get_library(player).get_all())
    activate_loyalty_ability(game, player, card, 0)
    assert card.loyalty == 8 and player.mana_pool.total() == 0
    resolve_stack(game)
    assert player.mana_pool.get(ManaType.RED) == 3
    assert len(game.get_exile(player).get_all()) == 3
    assert len(game.get_library(player).get_all()) == before - 3
    assert not game.get_hand(player).get_all()


def test_plus_two_handles_fewer_than_three_library_cards():
    game = create_game()
    player = game.players[0]
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    player.set_baseline(Intent(pattern=GameRef()))
    top = Creature(name="Only card", base_power=1, base_toughness=1, owner=player)
    game.get_library(player).add(top)
    card = enter_permanent(game, player, ChandraFlameshaper())
    activate_loyalty_ability(game, player, card, 0)
    resolve_stack(game)
    assert game.get_exile(player).get_all() == [top]
    assert not game.get_library(player).get_all()
    assert player.mana_pool.get(ManaType.RED) == 3


def test_plus_two_cannot_be_repeated_in_the_same_turn():
    game = behavioral_game()
    player = game.players[0]
    card = enter_permanent(game, player, ChandraFlameshaper())
    activate_loyalty_ability(game, player, card, 0)
    resolve_stack(game)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, card, 0)
    assert card.loyalty == 8 and player.mana_pool.get(ManaType.RED) == 3
    assert len(game.get_exile(player).get_all()) == 3
