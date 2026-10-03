import pytest
from card_impl import BilboThiefintheNight
from engine.card import Artifact, Creature, Instant, Sorcery
from engine.casting import CastingError
from engine.casting import cast_spell as cast
from engine.combat import declare_attackers_step
from engine.decisions import Decision
from engine.game import sacrifice
from engine.stack import move_spell_off_stack, resolve_top_of_stack
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import enter_permanent, object_preference, prefer, resolve_stack, scenario_game


def setup(spell_class=Instant, mana='{1}{U}', owner_seat=0):
    g = scenario_game()
    p, q = g.players
    bilbo = enter_permanent(g, p, BilboThiefintheNight())
    bilbo.summoning_sick = False
    spell = spell_class(name='Borrowed spell', mana_cost=ManaCost.parse(mana), owner=g.players[owner_seat])
    g.players[owner_seat].zones[Zone.GRAVEYARD].add(spell)
    g.phase, g.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    prefer(p, object_preference(g, spell))
    return g, p, q, bilbo, spell


def attack(g, bilbo):
    declare_attackers_step(g, [bilbo])


@pytest.mark.parametrize('kind', [Instant, Sorcery])
def test_graveyard_spell_pays_reduced_colored_cost_and_exiles(kind):
    g, p, _q, bilbo, spell = setup(kind)
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.EXILE].contains(spell)
    assert p.mana_pool.total() == 0


def test_artifact_returns_as_permanent_and_dies_normally():
    g, p, _q, bilbo, spell = setup(Artifact)
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.BATTLEFIELD].contains(spell)
    sacrifice(g, p, spell)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


@pytest.mark.parametrize('kind,owner_seat', [(Creature, 0), (Instant, 1)])
def test_attack_does_not_offer_ineligible_graveyard_cards(kind, owner_seat):
    g, p, _q, bilbo, spell = setup(kind, owner_seat=owner_seat)
    p.mana_pool.add(ManaType.BLUE, 5)
    attack(g, bilbo)
    resolve_stack(g)
    assert g.players[owner_seat].zones[Zone.GRAVEYARD].contains(spell)


def test_attack_cast_is_optional():
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE)
    prefer(p, Decision.no())
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)
    assert p.mana_pool.total() == 1


def test_reduction_does_not_remove_colored_cost():
    g, p, _q, bilbo, spell = setup(mana='{U}')
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


def test_spells_from_hand_receive_no_discount():
    g, p, _q, _bilbo, spell = setup()
    p.zones[Zone.GRAVEYARD].remove(spell)
    p.zones[Zone.HAND].add(spell)
    p.mana_pool.add(ManaType.BLUE)
    with pytest.raises(CastingError):
        cast(g, p, spell)
    assert p.zones[Zone.HAND].contains(spell)


def test_countered_graveyard_spell_is_exiled():
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_top_of_stack(g)
    pending = g.stack.peek()
    assert pending.source is spell
    move_spell_off_stack(g, pending)
    assert p.zones[Zone.EXILE].contains(spell)


def test_trigger_survives_bilbo_but_discount_does_not():
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE)
    p.mana_pool.add(ManaType.COLORLESS)
    attack(g, bilbo)
    sacrifice(g, p, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.EXILE].contains(spell)
    assert p.mana_pool.total() == 0


def test_other_attacker_does_not_trigger_bilbo():
    g, p, _q, _bilbo, spell = setup()
    creature = enter_permanent(g, p, Creature(name='Other attacker', base_power=2, base_toughness=2))
    creature.summoning_sick = False
    p.mana_pool.add(ManaType.BLUE)
    declare_attackers_step(g, [creature])
    resolve_stack(g)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


def test_permission_is_only_during_attack_trigger():
    g, p, _q, _bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE, 3)
    with pytest.raises(CastingError):
        cast(g, p, spell)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


def test_return_to_hand_does_not_exile_bilbo_spell():
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_top_of_stack(g)
    move_spell_off_stack(g, g.stack.peek(), Zone.HAND)
    assert p.zones[Zone.HAND].contains(spell)
    assert not p.zones[Zone.EXILE].contains(spell)


def test_attack_casts_only_one_spell():
    g, p, _q, bilbo, spell = setup()
    other = Instant(name='Unchosen', owner=p)
    p.zones[Zone.GRAVEYARD].add(other)
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.EXILE].contains(spell)
    assert p.zones[Zone.GRAVEYARD].contains(other)


def test_chosen_spell_leaving_before_trigger_resolves_cannot_be_cast():
    from engine.zones import move_to_zone
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    move_to_zone(g, spell, Zone.GRAVEYARD, Zone.EXILE)
    resolve_stack(g)
    assert p.zones[Zone.EXILE].contains(spell)
    assert p.mana_pool.total() == 1


def test_artifact_creature_is_an_eligible_attack_spell():
    from engine.card import ArtifactCreature
    g, p, _q, bilbo, spell = setup(ArtifactCreature)
    spell.base_power = spell.base_toughness = 2
    p.mana_pool.add(ManaType.BLUE)
    attack(g, bilbo)
    resolve_stack(g)
    assert p.zones[Zone.BATTLEFIELD].contains(spell)
    assert p.mana_pool.total() == 0


@pytest.mark.parametrize('generic_mana,cast_succeeds', [(0, False), (1, True)])
def test_opponents_nonhand_spell_receives_no_discount(generic_mana, cast_succeeds):
    g, p, q, bilbo, spell = setup(owner_seat=1)
    opposing_bilbo = enter_permanent(g, q, BilboThiefintheNight())
    opposing_bilbo.summoning_sick = False
    g.active_player_index = 1
    prefer(q, object_preference(g, spell))
    q.mana_pool.add(ManaType.BLUE)
    q.mana_pool.add(ManaType.COLORLESS, generic_mana)
    attack(g, opposing_bilbo)
    # Its trigger grants the cast; only the other player's discount survives.
    sacrifice(g, q, opposing_bilbo)
    resolve_stack(g)
    expected_zone = Zone.EXILE if cast_succeeds else Zone.GRAVEYARD
    assert q.zones[expected_zone].contains(spell)
    assert q.mana_pool.total() == (0 if cast_succeeds else 1)
    assert p.zones[Zone.BATTLEFIELD].contains(bilbo)


def test_declining_trigger_does_not_leave_cast_permission():
    g, p, _q, bilbo, spell = setup()
    p.mana_pool.add(ManaType.BLUE, 3)
    prefer(p, Decision.no())
    attack(g, bilbo)
    resolve_stack(g)
    with pytest.raises(CastingError):
        cast(g, p, spell)
    assert p.zones[Zone.GRAVEYARD].contains(spell)
