"""Drake Hatcher earns counters through combat and pays them through activation."""

import pytest
from cards.fdn.fdn_35.card_impl import DrakeHatcher
from engine.abilities import AbilityError
from engine.combat import combat_damage_step
from engine.game import add_counter
from engine.protection import get_colors
from engine.types import Color, Keyword
from test_utils import (
    activate_card_ability,
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
    resolve_stack,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    card = enter_permanent(game, player, DrakeHatcher())
    return game, player, card


def test_combat_damage_adds_engine_counters():
    game, _player, card = arrange()
    card.summoning_sick = False
    add_counter(game, card, "+1/+1", 2)
    declare_attackers(game, [card])
    declare_blockers(game, {})
    combat_damage_step(game)
    resolve_stack(game)
    assert game.players[1].life == 17
    assert card.counters.get("incubation") == 3


def test_ability_pays_three_counters_and_mints_drake():
    game, player, card = arrange()
    add_counter(game, card, "incubation", 4)
    activate_card_ability(game, player, card)
    resolve_stack(game)
    tokens = [c for c in game.get_battlefield(player).get_all() if getattr(c, "is_token", False)]
    assert len(tokens) == 1
    assert (tokens[0].power, tokens[0].toughness) == (2, 2)
    assert "Drake" in tokens[0].subtypes and tokens[0].keywords & Keyword.FLYING
    assert get_colors(tokens[0]) == {Color.BLUE}
    assert card.counters.get("incubation") == 1


def test_ability_unpayable_below_three_counters():
    game, player, card = arrange()
    add_counter(game, card, "incubation", 2)
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, card)
    assert card.counters.get("incubation") == 2
    assert not any(getattr(c, "is_token", False) for c in game.get_battlefield(player).get_all())
