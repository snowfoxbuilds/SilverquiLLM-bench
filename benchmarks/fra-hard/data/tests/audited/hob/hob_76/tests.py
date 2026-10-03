import pytest
from card_impl import InsideInformation
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import CastingError, play_land
from engine.casting import cast_spell as cast
from engine.decisions import Decision
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import cast_card, prefer, resolve_stack, scenario_game


def setup(kinds=(Instant,), costs=('{2}{U}',), x=None):
    g = scenario_game()
    p, q = g.players
    cards = [kind(name=f'Exiled {i}', mana_cost=ManaCost.parse(cost), owner=q)
             for i, (kind, cost) in enumerate(zip(kinds, costs))]
    for card in cards:
        if isinstance(card, Creature):
            card.base_power, card.base_toughness = 2, 2
        q.zones[Zone.LIBRARY].add(card)
    x = len(cards) if x is None else x
    p.mana_pool.add(ManaType.BLACK, 2)
    p.mana_pool.add(ManaType.COLORLESS, x)
    prefer(p, Decision.number(x))
    cast_card(g, p, InsideInformation())
    return g, p, q, cards


def test_x_exiles_exact_top_cards_and_pays_x():
    _g, p, q, cards = setup((Instant, Instant, Instant), ('{1}', '{2}', '{3}'), x=2)
    assert q.zones[Zone.LIBRARY].get_all() == cards[:1]
    assert set(q.zones[Zone.EXILE].get_all()) == set(cards[1:])
    assert len(q.zones[Zone.EXILE]) == 2
    assert p.mana_pool.total() == 0


def test_x_zero_exiles_nothing():
    _g, _p, q, cards = setup(x=0)
    assert q.zones[Zone.LIBRARY].contains(cards[0])
    assert len(q.zones[Zone.EXILE]) == 0


@pytest.mark.parametrize('kind', [Instant, Sorcery, Creature])
def test_casting_exiled_spell_pays_mana_value_in_life(kind):
    g, p, q, cards = setup((kind,))
    card = cards[0]
    cast(g, p, card)
    resolve_stack(g)
    assert p.life == 17
    assert p.mana_pool.total() == 0
    expected = p.zones[Zone.BATTLEFIELD] if kind is Creature else q.zones[Zone.GRAVEYARD]
    assert expected.contains(card)


def test_land_play_does_not_pay_life_and_consumes_land_play():
    g, p, _q, cards = setup((Land,), ('{0}',))
    play_land(g, p, cards[0])
    assert p.zones[Zone.BATTLEFIELD].contains(cards[0])
    assert p.life == 20
    assert p.land_plays_remaining == 0


def test_opponent_does_not_gain_permission():
    g, _p, q, cards = setup()
    q.mana_pool.add(ManaType.BLUE, 8)
    with pytest.raises(CastingError):
        cast(g, q, cards[0])
    assert q.zones[Zone.EXILE].contains(cards[0])


def test_casting_obeys_sorcery_timing():
    g, p, _q, cards = setup((Sorcery,))
    g.phase, g.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    with pytest.raises(CastingError):
        cast(g, p, cards[0])
    assert p.life == 20


def test_permission_expires_after_turn():
    g, p, q, cards = setup()
    g.phase, g.step = Phase.ENDING, Step.CLEANUP
    g.advance_phase()
    with pytest.raises(CastingError):
        cast(g, p, cards[0])
    assert q.zones[Zone.EXILE].contains(cards[0])


def test_permission_tracks_exact_exile_stint():
    g, p, _q, cards = setup()
    card = cards[0]
    move_to_zone(g, card, Zone.EXILE, Zone.HAND)
    move_to_zone(g, card, Zone.HAND, Zone.EXILE)
    with pytest.raises(CastingError):
        cast(g, p, card)
    assert p.life == 20


def test_insufficient_life_does_not_pay_or_move_card():
    g, p, q, cards = setup(costs=('{30}',))
    with pytest.raises(CastingError):
        cast(g, p, cards[0])
    assert p.life == 20
    assert q.zones[Zone.EXILE].contains(cards[0])


def test_mana_is_not_used_instead_of_life():
    g, p, _q, cards = setup()
    p.mana_pool.add(ManaType.BLUE, 8)
    cast(g, p, cards[0])
    resolve_stack(g)
    assert p.life == 17
    assert p.mana_pool.total() == 8


def test_can_play_multiple_exiled_spells():
    g, p, q, cards = setup((Instant, Instant), ('{2}', '{3}'))
    for card in cards:
        cast(g, p, card)
        resolve_stack(g)
    assert p.life == 15
    assert all(q.zones[Zone.GRAVEYARD].contains(card) for card in cards)


def test_x_spell_cast_using_life_has_x_zero():
    g, p, _q, cards = setup((Sorcery,), ('{X}{B}',))
    p.mana_pool.add(ManaType.BLACK, 8)
    prefer(p, Decision.number(5))
    cast(g, p, cards[0])
    resolve_stack(g)
    assert p.life == 19
    assert p.mana_pool.total() == 8


def test_x_larger_than_library_exiles_available_cards_without_drawing():
    _g, _p, q, cards = setup(x=5)
    assert q.zones[Zone.EXILE].get_all() == cards
    assert len(q.zones[Zone.LIBRARY]) == 0
    assert not q.drawn_from_empty_library


def test_zero_mana_value_spell_costs_zero_life():
    g, p, q, cards = setup(costs=('{0}',))
    cast(g, p, cards[0])
    resolve_stack(g)
    assert p.life == 20
    assert q.zones[Zone.GRAVEYARD].contains(cards[0])


def test_can_pay_exact_remaining_life():
    g, p, _q, cards = setup(costs=('{20}',))
    cast(g, p, cards[0])
    assert p.life == 0
    assert g.stack.peek().source is cards[0]


def test_second_exiled_land_cannot_exceed_land_play_limit():
    g, p, q, cards = setup((Land, Land), ('{0}', '{0}'))
    play_land(g, p, cards[0])
    with pytest.raises(CastingError):
        play_land(g, p, cards[1])
    assert q.zones[Zone.EXILE].contains(cards[1])
    assert p.life == 20


def test_sorcery_cannot_be_cast_with_another_spell_on_stack():
    g, p, q, cards = setup((Instant, Sorcery), ('{1}', '{2}'))
    cast(g, p, cards[0])
    with pytest.raises(CastingError):
        cast(g, p, cards[1])
    assert q.zones[Zone.EXILE].contains(cards[1])
    assert p.life == 19


def test_countered_exiled_spell_does_not_refund_life():
    from engine.stack import move_spell_off_stack
    g, p, q, cards = setup()
    pending = cast(g, p, cards[0])
    move_spell_off_stack(g, pending)
    assert p.life == 17
    assert q.zones[Zone.GRAVEYARD].contains(cards[0])
