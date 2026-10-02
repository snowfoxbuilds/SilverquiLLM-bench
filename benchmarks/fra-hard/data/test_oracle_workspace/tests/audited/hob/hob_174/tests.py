import pytest
from card_impl import GlamdringFoehammer
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError
from engine.casting import cast_spell as cast
from engine.decisions import Decision
from engine.stack import move_spell_off_stack
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
    scenario_game,
)


def setup():
    g = scenario_game()
    g.phase = Phase.PRECOMBAT_MAIN
    p, q = g.players
    sword = GlamdringFoehammer(owner=p)
    p.zones[Zone.HAND].add(sword)
    return g, p, q, sword


def library(p):
    cards = [Creature(name='Bottom', owner=p, base_power=1, base_toughness=1),
             Instant(name='Instant A', owner=p), Creature(name='Creature', owner=p, base_power=1, base_toughness=1),
             Sorcery(name='Sorcery', owner=p), Creature(name='Other creature', owner=p, base_power=1, base_toughness=1),
             Instant(name='Instant B', owner=p), Creature(name='Top', owner=p, base_power=1, base_toughness=1)]
    for card in cards:
        p.zones[Zone.LIBRARY].add(card)
    return cards


def adventure(g, p, sword, resolve=True):
    p.mana_pool.add(ManaType.BLUE)
    p.mana_pool.add(ManaType.COLORLESS, 3)
    prefer(p, Decision.yes())
    pending = cast(g, p, sword)
    if resolve:
        resolve_stack(g)
    return pending


def test_front_face_casts_as_equipment_without_milling():
    g, p, _q, sword = setup()
    library(p)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    prefer(p, Decision.no())
    cast(g, p, sword)
    resolve_stack(g)
    assert p.zones[Zone.BATTLEFIELD].contains(sword)
    assert sword.card_types == {CardType.ARTIFACT}
    assert len(p.zones[Zone.LIBRARY]) == 7


def test_adventure_mills_six_and_recovers_only_instants_and_sorceries():
    g, p, _q, sword = setup()
    cards = library(p)
    adventure(g, p, sword)
    assert p.zones[Zone.LIBRARY].get_all() == cards[:1]
    assert set(p.zones[Zone.HAND].get_all()) == {cards[1], cards[3], cards[5]}
    assert set(p.zones[Zone.GRAVEYARD].get_all()) == {cards[2], cards[4], cards[6]}
    assert p.zones[Zone.EXILE].contains(sword)
    assert sword.name == 'Glamdring, Foe-hammer'


def test_adventure_can_then_cast_front_face_from_exile():
    g, p, _q, sword = setup()
    adventure(g, p, sword)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    cast(g, p, sword)
    resolve_stack(g)
    assert p.zones[Zone.BATTLEFIELD].contains(sword)
    assert sword.card_types == {CardType.ARTIFACT}


def test_countered_adventure_goes_to_graveyard_and_has_no_exile_permission():
    g, p, _q, sword = setup()
    library(p)
    pending = adventure(g, p, sword, resolve=False)
    move_spell_off_stack(g, pending)
    assert p.zones[Zone.GRAVEYARD].contains(sword)
    assert sword.card_types == {CardType.ARTIFACT}
    assert len(p.zones[Zone.LIBRARY]) == 7
    with pytest.raises(CastingError):
        cast(g, p, sword)


def test_exile_from_other_effect_does_not_grant_adventure_permission():
    g, p, _q, sword = setup()
    move_to_zone(g, sword, Zone.HAND, Zone.EXILE)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    prefer(p, Decision.no())
    with pytest.raises(CastingError):
        cast(g, p, sword)
    assert p.zones[Zone.EXILE].contains(sword)


def test_adventure_exile_permission_expires_after_zone_change():
    g, p, _q, sword = setup()
    adventure(g, p, sword)
    move_to_zone(g, sword, Zone.EXILE, Zone.HAND)
    move_to_zone(g, sword, Zone.HAND, Zone.EXILE)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    prefer(p, Decision.no())
    with pytest.raises(CastingError):
        cast(g, p, sword)


def equip(g, p, sword, power=3):
    p.zones[Zone.HAND].remove(sword)
    enter_permanent(g, p, sword)
    bearer = enter_permanent(g, p, Creature(name='Bearer', base_power=power, base_toughness=5))
    p.mana_pool.add(ManaType.COLORLESS, 2)
    prefer(p, object_preference(g, bearer))
    activate_card_ability(g, p, sword)
    resolve_stack(g)
    assert sword.attached_to is bearer
    return bearer


@pytest.mark.parametrize('kind', [Instant, Sorcery])
def test_equipped_power_reduces_instant_and_sorcery_generic_cost(kind):
    g, p, _q, sword = setup()
    equip(g, p, sword)
    p.mana_pool.add(ManaType.BLUE)
    spell = kind(name='Discounted', mana_cost=ManaCost.parse('{3}{U}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    cast(g, p, spell)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)
    assert p.mana_pool.total() == 0


def test_discount_does_not_reduce_colored_mana():
    g, p, _q, sword = setup()
    equip(g, p, sword, power=10)
    spell = Instant(name='Colored', mana_cost=ManaCost.parse('{U}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    with pytest.raises(CastingError):
        cast(g, p, spell)


def test_unequipped_equipment_does_not_discount():
    g, p, _q, sword = setup()
    p.zones[Zone.HAND].remove(sword)
    enter_permanent(g, p, sword)
    spell = Instant(name='Undiscounted', mana_cost=ManaCost.parse('{2}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    with pytest.raises(CastingError):
        cast(g, p, spell)


def test_discount_does_not_apply_to_creature_spell():
    g, p, _q, sword = setup()
    equip(g, p, sword)
    spell = Creature(name='Creature spell', mana_cost=ManaCost.parse('{3}'), owner=p,
                     base_power=1, base_toughness=1)
    p.zones[Zone.HAND].add(spell)
    with pytest.raises(CastingError):
        cast(g, p, spell)


def test_equipped_creature_leaving_ends_discount():
    g, p, _q, sword = setup()
    bearer = equip(g, p, sword)
    move_to_zone(g, bearer, Zone.BATTLEFIELD, Zone.HAND)
    spell = Instant(name='Undiscounted', mana_cost=ManaCost.parse('{3}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    with pytest.raises(CastingError):
        cast(g, p, spell)


def test_adventure_does_not_return_older_graveyard_spells():
    g, p, _q, sword = setup()
    old = Instant(name='Old', owner=p)
    p.zones[Zone.GRAVEYARD].add(old)
    adventure(g, p, sword)
    assert p.zones[Zone.GRAVEYARD].contains(old)


def test_adventure_short_library_does_not_draw_from_empty():
    g, p, _q, sword = setup()
    card = Instant(name='Only', owner=p)
    p.zones[Zone.LIBRARY].add(card)
    adventure(g, p, sword)
    assert p.zones[Zone.HAND].contains(card)
    assert not p.drawn_from_empty_library


def test_free_cast_from_graveyard_can_choose_adventure():
    from engine.casting import cast_spell_free
    g, p, _q, sword = setup()
    cards = library(p)
    move_to_zone(g, sword, Zone.HAND, Zone.GRAVEYARD)
    prefer(p, Decision.yes())
    cast_spell_free(g, p, sword, Zone.GRAVEYARD)
    resolve_stack(g)
    assert p.zones[Zone.EXILE].contains(sword)
    assert set(p.zones[Zone.HAND].get_all()) == {cards[1], cards[3], cards[5]}


def test_failed_adventure_cast_restores_front_face_in_hand():
    g, p, _q, sword = setup()
    prefer(p, Decision.yes())
    with pytest.raises(CastingError):
        cast(g, p, sword)
    assert p.zones[Zone.HAND].contains(sword)
    assert sword.name == 'Glamdring, Foe-hammer'
    assert sword.card_types == {CardType.ARTIFACT}


def test_equipped_creature_power_changes_discount():
    from engine.game import add_counter
    g, p, _q, sword = setup()
    bearer = equip(g, p, sword, power=2)
    add_counter(g, bearer, '+1/+1', 2)
    spell = Instant(name='Four mana spell', mana_cost=ManaCost.parse('{4}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    cast(g, p, spell)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


def test_opponents_spell_receives_no_discount():
    g, p, q, sword = setup()
    equip(g, p, sword)
    spell = Instant(name='Opponent spell', mana_cost=ManaCost.parse('{3}'), owner=q)
    q.zones[Zone.HAND].add(spell)
    with pytest.raises(CastingError):
        cast(g, q, spell)


def test_negative_power_does_not_increase_cost():
    g, p, _q, sword = setup()
    equip(g, p, sword, power=-2)
    spell = Instant(name='One mana spell', mana_cost=ManaCost.parse('{1}'), owner=p)
    p.zones[Zone.HAND].add(spell)
    p.mana_pool.add(ManaType.COLORLESS)
    cast(g, p, spell)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)
