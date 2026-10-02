import pytest
from card_impl import SupperforSpiders
from engine.card import Creature
from engine.game import sacrifice
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    cast_card,
    enter_permanent,
    resolve_stack,
    scenario_game,
)


def creature(name='Victim'):
    return Creature(name=name, base_power=2, base_toughness=2, subtypes={'Elf'},
                    supertypes={Supertype.LEGENDARY}, mana_cost=ManaCost.parse('{1}{G}'))


def setup():
    g = scenario_game()
    p, q = g.players
    victim = enter_permanent(g, q, creature())
    sacrifice(g, q, victim)
    return g, p, q, victim


def supper(g, p):
    p.mana_pool.add(ManaType.BLACK)
    p.mana_pool.add(ManaType.COLORLESS)
    cast_card(g, p, SupperforSpiders())


def test_returns_opponents_dead_creature_as_food_under_caster_control():
    g, p, q, victim = setup()
    supper(g, p)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)
    assert victim.controller is p and victim.owner is q
    assert victim.card_types == {CardType.ARTIFACT}
    assert victim.subtypes == {'Food'}
    assert Supertype.LEGENDARY in victim.supertypes


def test_food_ability_pays_mana_sacrifices_and_gains_three():
    g, p, q, victim = setup()
    supper(g, p)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    activate_card_ability(g, p, victim)
    assert q.zones[Zone.GRAVEYARD].contains(victim)
    assert p.life == 20
    resolve_stack(g)
    assert p.life == 23
    assert p.mana_pool.total() == 0


@pytest.mark.parametrize('tapped,mana', [(True, 2), (False, 1)])
def test_food_cannot_activate_without_costs(tapped, mana):
    from engine.abilities import AbilityError
    g, p, _q, victim = setup()
    supper(g, p)
    victim.is_tapped = tapped
    p.mana_pool.add(ManaType.COLORLESS, mana)
    with pytest.raises(AbilityError):
        activate_card_ability(g, p, victim)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)
    assert p.life == 20


def test_casters_own_dead_creature_is_not_returned():
    g, p, _q, victim = setup()
    own = enter_permanent(g, p, creature('Own'))
    sacrifice(g, p, own)
    supper(g, p)
    assert p.zones[Zone.GRAVEYARD].contains(own)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)


def test_discarded_creature_is_not_returned():
    g, p, q, _victim = setup()
    discarded = creature('Discarded')
    discarded.owner = discarded.controller = q
    q.zones[Zone.HAND].add(discarded)
    move_to_zone(g, discarded, Zone.HAND, Zone.GRAVEYARD)
    supper(g, p)
    assert q.zones[Zone.GRAVEYARD].contains(discarded)


def test_previous_turn_death_is_not_returned():
    g, p, q, victim = setup()
    g.phase, g.step = Phase.ENDING, Step.CLEANUP
    g.advance_phase()
    supper(g, p)
    assert q.zones[Zone.GRAVEYARD].contains(victim)


def test_death_then_leave_graveyard_and_return_is_new_object():
    g, p, q, victim = setup()
    move_to_zone(g, victim, Zone.GRAVEYARD, Zone.HAND)
    move_to_zone(g, victim, Zone.HAND, Zone.GRAVEYARD)
    supper(g, p)
    assert q.zones[Zone.GRAVEYARD].contains(victim)


def test_returns_multiple_creatures():
    g, p, q, victim = setup()
    other = enter_permanent(g, q, Creature(name='Other', base_power=3, base_toughness=3))
    sacrifice(g, q, other)
    supper(g, p)
    assert all(p.zones[Zone.BATTLEFIELD].contains(c) for c in (victim, other))
    assert all(c.card_types == {CardType.ARTIFACT} for c in (victim, other))


def test_food_survives_recalculation_and_cleanup():
    from test_utils import finish_cleanup
    g, p, _q, victim = setup()
    supper(g, p)
    finish_cleanup(g)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)
    assert victim.card_types == {CardType.ARTIFACT}
    assert victim.subtypes == {'Food'}


def test_food_restores_printed_creature_when_leaving_battlefield():
    g, p, q, victim = setup()
    supper(g, p)
    move_to_zone(g, victim, Zone.BATTLEFIELD, Zone.HAND)
    assert q.zones[Zone.HAND].contains(victim)
    assert victim.card_types == {CardType.CREATURE}
    assert victim.subtypes == {'Elf'}


def test_opponent_owned_creature_dying_under_your_control_is_eligible():
    g = scenario_game()
    p, q = g.players
    victim = creature()
    victim.owner, victim.controller = q, p
    p.zones[Zone.HAND].add(victim)
    move_to_zone(g, victim, Zone.HAND, Zone.BATTLEFIELD)
    sacrifice(g, p, victim)
    supper(g, p)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)


def test_returned_card_keeps_its_other_abilities():
    from engine.card import ActivatedAbility
    from engine.game import gain_life

    class Healer(Creature):
        def get_activated_abilities(self):
            return [ActivatedAbility(cost=lambda g, s: True,
                                     effect=lambda g: gain_life(g, self.controller, 1))]
    g = scenario_game()
    p, q = g.players
    victim = enter_permanent(g, q, Healer(name='Healer', base_power=1, base_toughness=1))
    sacrifice(g, q, victim)
    supper(g, p)
    activate_card_ability(g, p, victim, 0)
    resolve_stack(g)
    assert p.life == 21


def test_food_ability_benefits_its_new_controller():
    g, p, q, victim = setup()
    supper(g, p)
    p.zones[Zone.BATTLEFIELD].remove(victim)
    q.zones[Zone.BATTLEFIELD].add(victim)
    victim.controller = q
    q.mana_pool.add(ManaType.COLORLESS, 2)
    activate_card_ability(g, q, victim)
    resolve_stack(g)
    assert q.life == 23 and p.life == 20


def test_dead_creature_tokens_are_not_returned():
    from engine.game import create_token
    g = scenario_game()
    p, q = g.players
    token = creature('Token')
    create_token(g, q, token)
    sacrifice(g, q, token)
    supper(g, p)
    assert not p.zones[Zone.BATTLEFIELD].contains(token)


def test_food_cannot_attack():
    from engine.combat import declare_attackers_step
    g, p, _q, victim = setup()
    supper(g, p)
    victim.summoning_sick = False
    g.phase, g.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
    declare_attackers_step(g, [victim])
    assert not victim.is_attacking


def test_noncreature_artifact_put_in_graveyard_is_not_returned():
    from engine.card import Artifact
    g, p, q, _victim = setup()
    artifact = enter_permanent(g, q, Artifact(name='Broken relic'))
    sacrifice(g, q, artifact)
    supper(g, p)
    assert q.zones[Zone.GRAVEYARD].contains(artifact)


def test_your_card_dying_under_opponent_control_is_not_returned():
    g, p, q, _victim = setup()
    own = creature('Stolen')
    own.owner, own.controller = p, q
    q.zones[Zone.HAND].add(own)
    move_to_zone(g, own, Zone.HAND, Zone.BATTLEFIELD)
    sacrifice(g, q, own)
    supper(g, p)
    assert p.zones[Zone.GRAVEYARD].contains(own)


def test_sacrificed_food_can_be_returned_by_a_second_supper():
    g, p, q, victim = setup()
    supper(g, p)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    activate_card_ability(g, p, victim)
    resolve_stack(g)
    assert q.zones[Zone.GRAVEYARD].contains(victim)
    supper(g, p)
    assert p.zones[Zone.BATTLEFIELD].contains(victim)
    assert victim.card_types == {CardType.ARTIFACT}
    assert victim.subtypes == {'Food'}


def test_returned_food_fires_its_enter_trigger():
    from engine.events import EntersBattlefieldTriggeredEvent
    from engine.game import gain_life
    from engine.triggers import TriggerRegistration

    class Welcomer(Creature):
        def register_triggers(self, game):
            game.trigger_manager.register(TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent, source=self,
                controller=self.controller,
                condition=lambda g, event: event.permanent is self,
                effect=lambda g, controller: gain_life(g, controller, 2)))
    g = scenario_game()
    p, q = g.players
    victim = enter_permanent(g, q, Welcomer(name='Welcomer', base_power=1, base_toughness=1))
    resolve_stack(g)
    sacrifice(g, q, victim)
    supper(g, p)
    assert p.life == 22 and q.life == 22


def test_leaving_food_loses_granted_activated_ability():
    from test_utils import card_abilities
    g, p, _q, victim = setup()
    supper(g, p)
    move_to_zone(g, victim, Zone.BATTLEFIELD, Zone.HAND)
    assert card_abilities(victim) == []


def test_food_ability_countered_keeps_cost_paid_without_life_gain():
    g, p, q, victim = setup()
    supper(g, p)
    p.mana_pool.add(ManaType.COLORLESS, 2)
    activate_card_ability(g, p, victim)
    g.stack.pop()
    resolve_stack(g)
    assert p.life == 20
    assert p.mana_pool.total() == 0
    assert q.zones[Zone.GRAVEYARD].contains(victim)
