import pytest
from engine.card import Creature
from engine.decisions import Decision
from engine.game import exile
from engine.types import Keyword, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_spell,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def bear(game, player, name="Bear", power=2):
    return put_on_battlefield(game, player, Creature(name=name, base_power=power, base_toughness=4))


def fund(player, **amounts):
    for name, amount in amounts.items():
        player.mana_pool.add(ManaType[name], amount)


from card_impl import TheEaglesAreComing
from engine.protection import get_colors
from engine.types import Color
from test_utils import TestSetupError as SetupError


def arrange(kicked=False, count=1):
    game = behavioral_game()
    p = game.players[0]
    creatures = [bear(game, p, f"Bear {i}") for i in range(count)]
    card = TheEaglesAreComing(owner=p)
    game.get_hand(p).add(card)
    fund(p, WHITE=3 if kicked else 1, COLORLESS=3 if kicked else 1)
    prefer(
        p,
        Decision.yes() if kicked else Decision.no(),
        *(object_preference(game, c) for c in creatures),
    )
    return game, p, card, creatures


def birds(game, p):
    return [c for c in game.get_battlefield(p).get_all() if c.name == "Bird Soldier"]


def test_unkicked_returns_one_then_creates_bird_next_upkeep():
    game, p, card, creatures = arrange()
    cast_spell(game, 0, card.name)
    assert p.zones[Zone.HAND].contains(creatures[0])
    assert not birds(game, p)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert len(birds(game, p)) == 1
    token = birds(game, p)[0]
    assert (token.power, token.toughness) == (4, 4)
    assert token.keywords & Keyword.FLYING
    assert token.subtypes == {"Bird", "Soldier"}
    assert get_colors(token) == {Color.WHITE}


@pytest.mark.parametrize("count", [1, 2, 3])
def test_kicker_returns_any_number_and_pays_both_costs(count):
    game, p, card, creatures = arrange(True, count)
    cast_spell(game, 0, card.name)
    assert p.mana_pool.total() == 0
    assert all(p.zones[Zone.HAND].contains(c) for c in creatures)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert len(birds(game, p)) == count


def test_kicked_can_choose_zero_targets():
    game, p, card, _ = arrange(True, 0)
    cast_spell(game, 0, card.name)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert not birds(game, p)


def test_delayed_trigger_fires_only_once():
    game, p, card, _ = arrange()
    cast_spell(game, 0, card.name)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert len(birds(game, p)) == 1


def test_removed_target_produces_no_bird():
    from engine.casting import cast_spell as cast

    game, p, card, creatures = arrange()
    cast(game, p, card)
    exile(game, creatures[0])
    resolve_stack(game)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert not birds(game, p)


def test_partial_resolution_counts_only_returned_creatures():
    from engine.casting import cast_spell as cast

    game, p, card, creatures = arrange(True, 2)
    cast(game, p, card)
    exile(game, creatures[0])
    resolve_stack(game)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert len(birds(game, p)) == 1


def test_kicker_cannot_be_paid_with_only_normal_mana():
    game, p, card, _ = arrange()
    prefer(p, Decision.yes())
    with pytest.raises(SetupError):
        cast_spell(game, 0, card.name)
    assert p.mana_pool.total() == 2


def test_owns_target_even_when_an_opponent_controls_it():
    game, p, card, creatures = arrange()
    target = creatures[0]
    opponent = game.players[1]
    game.get_battlefield(p).remove(target)
    game.get_battlefield(opponent).add(target)
    target.controller = opponent
    prefer(p, Decision.no(), object_preference(game, target))
    cast_spell(game, 0, card.name)
    assert p.zones[Zone.HAND].contains(target)


def test_free_cast_still_pays_kicker():
    from engine.casting import cast_spell_free

    game, p, card, creatures = arrange(True, 2)
    p.mana_pool.empty()
    fund(p, WHITE=2, COLORLESS=2)
    cast_spell_free(game, p, card, Zone.HAND)
    resolve_stack(game)
    assert p.mana_pool.total() == 0
    assert all(p.zones[Zone.HAND].contains(c) for c in creatures)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert len(birds(game, p)) == 2


def test_returned_target_with_a_new_zone_stint_is_illegal():
    from engine.casting import cast_spell as cast

    game, p, card, creatures = arrange()
    target = creatures[0]
    cast(game, p, card)
    exile(game, target)
    move_to_zone(game, target, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert game.get_battlefield(p).contains(target)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    assert not birds(game, p)
