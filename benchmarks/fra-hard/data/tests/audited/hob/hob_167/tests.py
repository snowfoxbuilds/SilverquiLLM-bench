import pytest
from card_impl import ThranduiltheElvenking
from engine.card import ActivatedAbility, Creature, ManaAbility
from engine.game import gain_life
from engine.types import ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    card_abilities,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
    scenario_game,
)


class ElvenHealer(Creature):
    def __init__(self, **kwargs):
        super().__init__(name='Elven Healer', subtypes={'Elf'}, base_power=1, base_toughness=1, **kwargs)

    def get_activated_abilities(self):
        def cost(game, source):
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True
        return [ActivatedAbility(cost=cost, effect=lambda game: gain_life(game, self.controller, 2),
                                 description='Tap: gain two life')]


class ElvenMana(Creature):
    def __init__(self, **kwargs):
        super().__init__(name='Elven Mana', subtypes={'Elf'}, base_power=1, base_toughness=1, **kwargs)

    def get_mana_abilities(self):
        def cost(game, source):
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True
        return [ManaAbility(cost=cost, mana_produced=lambda game: self.controller.mana_pool.add(ManaType.GREEN))]


def setup(donor_class=ElvenHealer):
    g = scenario_game()
    p, q = g.players
    king = enter_permanent(g, p, ThranduiltheElvenking())
    donor = donor_class(owner=p)
    p.zones[Zone.GRAVEYARD].add(donor)
    return g, p, q, king, donor


def test_borrowed_ability_uses_thranduil_for_tap_and_controller():
    g, p, q, king, donor = setup()
    activate_card_ability(g, p, king)
    assert king.is_tapped and not donor.is_tapped
    assert p.life == 20
    resolve_stack(g)
    assert p.life == 22 and q.life == 20


def test_borrows_mana_abilities():
    g, p, _q, king, donor = setup(ElvenMana)
    activate_card_ability(g, p, king)
    assert p.mana_pool.get(ManaType.GREEN) == 1
    assert g.stack.is_empty()
    assert king.is_tapped and not donor.is_tapped


def test_ability_disappears_when_elf_leaves_graveyard():
    g, _p, _q, king, donor = setup()
    assert len(card_abilities(king)) == 1
    move_to_zone(g, donor, Zone.GRAVEYARD, Zone.EXILE)
    assert card_abilities(king) == []


def test_already_activated_ability_survives_donor_leaving():
    g, p, _q, king, donor = setup()
    activate_card_ability(g, p, king)
    move_to_zone(g, donor, Zone.GRAVEYARD, Zone.EXILE)
    resolve_stack(g)
    assert p.life == 22


@pytest.mark.parametrize('where,elf', [(Zone.HAND, True), (Zone.GRAVEYARD, False)])
def test_nonqualifying_card_does_not_grant_ability(where, elf):
    g, _p, _q, king, donor = setup()
    if where != Zone.GRAVEYARD:
        move_to_zone(g, donor, Zone.GRAVEYARD, where)
    if not elf:
        donor.subtypes = {'Human'}
    assert card_abilities(king) == []


def test_opponents_graveyard_does_not_grant_abilities():
    _g, p, q, king, donor = setup()
    p.zones[Zone.GRAVEYARD].remove(donor)
    donor.owner = donor.controller = q
    q.zones[Zone.GRAVEYARD].add(donor)
    assert card_abilities(king) == []


def test_new_elf_in_graveyard_grants_new_ability_immediately():
    g, p, _q, king, _donor = setup()
    mana = ElvenMana(owner=p)
    p.zones[Zone.GRAVEYARD].add(mana)
    activate_card_ability(g, p, king, 1)
    assert p.mana_pool.get(ManaType.GREEN) == 1


def test_activated_effect_survives_thranduil_leaving():
    g, p, _q, king, _donor = setup()
    activate_card_ability(g, p, king)
    move_to_zone(g, king, Zone.BATTLEFIELD, Zone.EXILE)
    resolve_stack(g)
    assert p.life == 22


def libraries(g, p):
    cards = [Creature(name=f'Draw {i}', owner=p, base_power=1, base_toughness=1) for i in range(3)]
    for card in cards:
        p.zones[Zone.LIBRARY].add(card)
    return cards


def test_another_legendary_elf_draws_two_then_discards_chosen_card():
    g, p, _q, _king, _donor = setup()
    cards = libraries(g, p)
    prefer(p, object_preference(g, cards[-1]))
    enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                                 subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    assert len(p.zones[Zone.HAND]) == 0
    resolve_stack(g)
    assert p.zones[Zone.HAND].get_all() == [cards[-2]]
    assert p.zones[Zone.GRAVEYARD].contains(cards[-1])
    assert len(p.zones[Zone.LIBRARY]) == 1


@pytest.mark.parametrize('elf,legendary,seat', [(False, True, 0), (True, False, 0), (True, True, 1)])
def test_nonqualifying_entry_does_not_draw(elf, legendary, seat):
    g, p, _q, _king, _donor = setup()
    libraries(g, p)
    enter_permanent(g, g.players[seat], Creature(name='Other', base_power=2, base_toughness=2,
                    subtypes={'Elf'} if elf else {'Human'},
                    supertypes={Supertype.LEGENDARY} if legendary else set()))
    resolve_stack(g)
    assert len(p.zones[Zone.HAND]) == 0
    assert len(p.zones[Zone.LIBRARY]) == 3


def test_thranduil_own_entry_does_not_draw():
    g = scenario_game()
    p, _q = g.players
    libraries(g, p)
    enter_permanent(g, p, ThranduiltheElvenking())
    resolve_stack(g)
    assert len(p.zones[Zone.HAND]) == 0


def test_trigger_remembers_controller_after_source_leaves():
    g, p, _q, king, _donor = setup()
    libraries(g, p)
    enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                    subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    move_to_zone(g, king, Zone.BATTLEFIELD, Zone.EXILE)
    resolve_stack(g)
    assert len(p.zones[Zone.HAND]) == 1
    assert len(p.zones[Zone.LIBRARY]) == 1


def test_ability_returns_when_donor_returns_to_graveyard():
    g, p, _q, king, donor = setup()
    assert len(card_abilities(king)) == 1
    move_to_zone(g, donor, Zone.GRAVEYARD, Zone.EXILE)
    assert card_abilities(king) == []
    move_to_zone(g, donor, Zone.EXILE, Zone.GRAVEYARD)
    assert len(card_abilities(king)) == 1
    activate_card_ability(g, p, king)
    assert king.is_tapped and not donor.is_tapped
    resolve_stack(g)
    assert p.life == 22


def test_thranduil_cannot_pay_borrowed_tap_cost_twice():
    from engine.abilities import AbilityError
    g, p, _q, king, _donor = setup()
    activate_card_ability(g, p, king)
    with pytest.raises(AbilityError):
        activate_card_ability(g, p, king)
    resolve_stack(g)
    assert p.life == 22


def test_borrowed_mana_can_pay_for_a_spell():
    from engine.card import Instant
    from engine.casting import cast_spell
    g, p, _q, king, _donor = setup(ElvenMana)
    spell = Instant(name='Green spell', owner=p, mana_cost=ManaCost.parse('{G}'))
    p.zones[Zone.HAND].add(spell)
    activate_card_ability(g, p, king)
    assert king.is_tapped and p.mana_pool.get(ManaType.GREEN) == 1
    cast_spell(g, p, spell)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)
    assert king.is_tapped
    assert p.mana_pool.total() == 0


def test_borrowed_ability_targets_and_resolves_against_chosen_permanent():
    from engine.card_queries import choose_object
    from engine.game import deal_damage

    class ElvenArcher(Creature):
        def get_activated_abilities(self):
            def targeting(game, source, controller):
                candidates = [card for player in game.players
                              for card in player.zones[Zone.BATTLEFIELD].get_all()
                              if isinstance(card, Creature)]
                return [choose_object(game, controller, candidates, 'target creature', source_card=self)]
            return [ActivatedAbility(cost=lambda g, s: True, targeting=targeting,
                    effect=lambda g, targets, context: deal_damage(g, self, targets[0], 1))]
    g = scenario_game()
    p, q = g.players
    king = enter_permanent(g, p, ThranduiltheElvenking())
    donor = ElvenArcher(name='Archer', subtypes={'Elf'}, owner=p, base_power=1, base_toughness=1)
    p.zones[Zone.GRAVEYARD].add(donor)
    target = enter_permanent(g, q, Creature(name='Target', base_power=2, base_toughness=2))
    prefer(p, object_preference(g, target))
    activate_card_ability(g, p, king)
    resolve_stack(g)
    assert target.damage_marked == 1


def test_borrowed_sacrifice_cost_sacrifices_thranduil_not_donor():
    from engine.game import sacrifice

    class ElvenMartyr(Creature):
        def get_activated_abilities(self):
            def cost(game, source):
                sacrifice(game, source.controller, source)
                return True
            return [ActivatedAbility(cost=cost, targeting=lambda g, s, p: [],
                    effect=lambda g, targets, context: gain_life(g, context.controller, 4))]
    g = scenario_game()
    p, _q = g.players
    king = enter_permanent(g, p, ThranduiltheElvenking())
    donor = ElvenMartyr(name='Martyr', subtypes={'Elf'}, owner=p, base_power=1, base_toughness=1)
    p.zones[Zone.GRAVEYARD].add(donor)
    activate_card_ability(g, p, king)
    assert p.zones[Zone.GRAVEYARD].contains(king)
    assert p.zones[Zone.GRAVEYARD].contains(donor)
    resolve_stack(g)
    assert p.life == 24


def test_noncreature_elf_card_still_grants_activated_abilities():
    from engine.types import CardType
    g, p, _q, king, donor = setup()
    donor.card_types = {CardType.ENCHANTMENT}
    activate_card_ability(g, p, king)
    resolve_stack(g)
    assert p.life == 22


def test_discard_may_choose_a_card_already_in_hand():
    g, p, _q, _king, _donor = setup()
    cards = libraries(g, p)
    old = Creature(name='Old hand card', owner=p, base_power=1, base_toughness=1)
    p.zones[Zone.HAND].add(old)
    prefer(p, object_preference(g, old))
    enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                                 subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(old)
    assert set(p.zones[Zone.HAND].get_all()) == set(cards[-2:])


def test_elf_leaving_after_entry_does_not_cancel_draw_trigger():
    g, p, _q, _king, _donor = setup()
    libraries(g, p)
    elf = enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                         subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    move_to_zone(g, elf, Zone.BATTLEFIELD, Zone.EXILE)
    resolve_stack(g)
    assert len(p.zones[Zone.HAND]) == 1
    assert len(p.zones[Zone.LIBRARY]) == 1


def test_losing_elf_subtype_removes_borrowed_ability():
    _g, _p, _q, king, donor = setup()
    assert len(card_abilities(king)) == 1
    donor.subtypes = {'Human'}
    assert card_abilities(king) == []
    assert not king.is_tapped


def test_new_controller_borrows_only_new_controllers_graveyard():
    g, p, q, king, _donor = setup()
    p.zones[Zone.BATTLEFIELD].remove(king)
    q.zones[Zone.BATTLEFIELD].add(king)
    king.controller = q
    assert card_abilities(king) == []
    q.zones[Zone.GRAVEYARD].add(ElvenMana(owner=q))
    activate_card_ability(g, q, king)
    assert q.mana_pool.get(ManaType.GREEN) == 1
    assert p.mana_pool.total() == 0


def test_draw_trigger_keeps_controller_when_thranduil_changes_control():
    g, p, q, king, _donor = setup()
    libraries(g, p)
    enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                    subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    p.zones[Zone.BATTLEFIELD].remove(king)
    q.zones[Zone.BATTLEFIELD].add(king)
    king.controller = q
    resolve_stack(g)
    assert len(p.zones[Zone.HAND]) == 1
    assert len(q.zones[Zone.HAND]) == 0
    assert not q.drawn_from_empty_library


def test_each_elf_card_grants_its_own_instance_of_same_ability():
    _g, p, _q, king, _donor = setup()
    p.zones[Zone.GRAVEYARD].add(ElvenHealer(owner=p))
    assert len(card_abilities(king)) == 2


def test_countering_draw_trigger_does_not_discard():
    g, p, _q, _king, _donor = setup()
    cards = libraries(g, p)
    old = Creature(name='Old hand card', owner=p, base_power=1, base_toughness=1)
    p.zones[Zone.HAND].add(old)
    enter_permanent(g, p, Creature(name='Legendary Elf', base_power=2, base_toughness=2,
                    subtypes={'Elf'}, supertypes={Supertype.LEGENDARY}))
    g.stack.pop()
    resolve_stack(g)
    assert p.zones[Zone.HAND].get_all() == [old]
    assert p.zones[Zone.LIBRARY].get_all() == cards
