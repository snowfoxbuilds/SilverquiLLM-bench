import pytest
from engine.card import Creature, Instant
from engine.game import add_counter, destroy
from engine.types import CardType, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    behavioral_game,
    cast_spell,
    enter_permanent,
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


from card_impl import TomBertAndWilliam
from engine.abilities import AbilityError


def arrange():
    game = behavioral_game()
    p = game.players[0]
    card = enter_permanent(game, p, TomBertAndWilliam())
    resolve_stack(game)
    return game, p, card


@pytest.mark.parametrize("power", [0, 1, 3, 6])
def test_sacrifice_draws_power_then_discards(power):
    game, p, card = arrange()
    victim = bear(game, p, "Victim", power)
    fund(p, COLORLESS=1)
    prefer(p, object_preference(game, victim))
    activate_card_ability(game, p, card)
    assert p.zones[Zone.GRAVEYARD].contains(victim)
    assert not game.get_hand(p).get_all()
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == max(0, power - 1)
    assert p.mana_pool.total() == 0


def test_power_includes_counters():
    game, p, card = arrange()
    victim = bear(game, p, "Victim", 2)
    add_counter(game, victim, "+1/+1", 2)
    fund(p, COLORLESS=1)
    prefer(p, object_preference(game, victim))
    activate_card_ability(game, p, card)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 3


def test_cannot_sacrifice_itself():
    game, p, card = arrange()
    fund(p, COLORLESS=1)
    with pytest.raises(AbilityError):
        activate_card_ability(game, p, card)
    assert game.get_battlefield(p).contains(card) and p.mana_pool.total() == 1


def test_unpayable_cost_does_not_sacrifice():
    game, p, card = arrange()
    victim = bear(game, p)
    with pytest.raises(AbilityError):
        activate_card_ability(game, p, card)
    assert game.get_battlefield(p).contains(victim)


def test_death_returns_as_legendary_noncreature_artifact():
    game, p, card = arrange()
    destroy(game, card)
    resolve_stack(game)
    assert game.get_battlefield(p).contains(card)
    assert card.card_types == {CardType.ARTIFACT}
    assert Supertype.LEGENDARY in card.supertypes
    assert "Troll" not in card.subtypes


def test_artifact_dying_does_not_return_again():
    game, p, card = arrange()
    destroy(game, card)
    resolve_stack(game)
    destroy(game, card)
    resolve_stack(game)
    assert p.zones[Zone.GRAVEYARD].contains(card)
    assert not game.get_battlefield(p).contains(card)


def test_exiling_in_response_prevents_return():
    game, p, card = arrange()
    destroy(game, card)
    move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)
    resolve_stack(game)
    assert p.zones[Zone.EXILE].contains(card)


def test_artifact_retains_sacrifice_ability():
    game, p, card = arrange()
    destroy(game, card)
    resolve_stack(game)
    victim = bear(game, p, "Victim", 3)
    prefer(p, object_preference(game, victim))
    fund(p, COLORLESS=1)
    activate_card_ability(game, p, card)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 2


def test_reusing_one_ability_keeps_each_activations_paid_power():
    from engine.abilities import ActivatedAbilityInstance, activate_ability

    game, p, card = arrange()
    small = bear(game, p, "Small", 1)
    large = bear(game, p, "Large", 4)
    descriptor = card.get_activated_abilities()[0]
    ability = ActivatedAbilityInstance(
        source=card, controller=p, cost=descriptor.cost, effect=descriptor.effect
    )
    fund(p, COLORLESS=2)
    prefer(p, object_preference(game, small))
    activate_ability(game, p, ability)
    prefer(p, object_preference(game, large))
    activate_ability(game, p, ability)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 3


def test_leaving_and_returning_clears_the_artifact_override():
    game, p, card = arrange()
    destroy(game, card)
    resolve_stack(game)
    move_to_zone(game, card, Zone.BATTLEFIELD, Zone.HAND)
    fund(p, BLACK=1, GREEN=1, COLORLESS=3)
    cast_spell(game, 0, card.name)
    assert card.card_types == {CardType.CREATURE} and "Troll" in card.subtypes


def test_zero_power_still_discards_from_an_existing_hand():
    game, p, card = arrange()
    victim = bear(game, p, "Zero", 0)
    spare = Instant(name="Spare", owner=p)
    game.get_hand(p).add(spare)
    prefer(p, object_preference(game, victim))
    fund(p, COLORLESS=1)
    activate_card_ability(game, p, card)
    resolve_stack(game)
    assert not game.get_hand(p).get_all() and p.zones[Zone.GRAVEYARD].contains(spare)


def test_returned_artifact_does_not_keep_creature_counters():
    game, _p, card = arrange()
    add_counter(game, card, "+1/+1", 2)
    destroy(game, card)
    resolve_stack(game)
    assert card.card_types == {CardType.ARTIFACT} and not card.counters
