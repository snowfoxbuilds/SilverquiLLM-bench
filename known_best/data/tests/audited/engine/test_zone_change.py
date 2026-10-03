"""A permanent that leaves the battlefield becomes a new object (rule 400.7).

It keeps none of its counters (122.2), status (110.5b, 110.5d), combat role
(506.4) or freedom from summoning sickness (302.6), and a token stops existing
(111.7, 704.5d). Abilities that refer to the object as it last existed on the
battlefield read its last-known information instead (603.10a, 608.2h), and an
effect locked onto it by a resolved spell or ability no longer applies to it
(611.2c).
"""

from __future__ import annotations

from engine.card import ActivatedAbility, Artifact, Creature
from engine.continuous_effects import DURATION_END_OF_TURN, DURATION_PERMANENT, ContinuousEffect, Layer, SubLayer
from engine.events import CreatureDiesTriggeredEvent, LeavesBattlefieldTriggeredEvent
from engine.game import add_counter, deal_damage, destroy, exile, gain_life, sacrifice, tap
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import TriggerRegistration
from engine.turn import untap_step
from engine.types import Zone
from engine.zones import move_to_zone
from test_utils import activate_card_ability, behavioral_game, declare_attackers, enter_permanent, resolve_stack


def _creature(name: str = "Test Creature", power: int = 1, toughness: int = 1) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _token(name: str = "Test Token") -> Creature:
    token = _creature(name)
    token.is_token = True
    return token


def _in_any_zone(game, obj) -> bool:
    return any(player.zones[zone].contains(obj) for player in game.players for zone in Zone)


def _with_two_plus_one_counters(game, player, card):
    enter_permanent(game, player, card)
    add_counter(game, card, "+1/+1", 2)
    return card


def test_counters_do_not_survive_leaving_the_battlefield():
    game = behavioral_game()
    p1 = game.players[0]
    creature = _with_two_plus_one_counters(game, p1, _creature())
    add_counter(game, creature, "charge", 1)
    assert creature.counters == {"+1/+1": 2, "charge": 1}

    destroy(game, creature)
    assert game.get_graveyard(p1).contains(creature)
    assert creature.counters == {}

    move_to_zone(game, creature, Zone.GRAVEYARD, Zone.BATTLEFIELD)
    assert game.get_battlefield(p1).contains(creature)
    assert creature.counters == {}
    assert creature.power == 1


def test_returned_permanent_enters_untapped():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature())
    tap(game, creature)

    exile(game, creature)
    move_to_zone(game, creature, Zone.EXILE, Zone.BATTLEFIELD)
    assert game.get_battlefield(p1).contains(creature)
    assert creature.is_tapped is False


def test_card_off_the_battlefield_has_no_status():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Attacker", 2, 3))
    untap_step(game)
    declare_attackers(game, ["Attacker"])
    deal_damage(game, _creature("Damage Source"), creature, 1)
    assert creature.is_attacking and creature.is_tapped and creature.damage_marked == 1

    destroy(game, creature)
    assert game.get_graveyard(p1).contains(creature)
    assert creature.is_tapped is False
    assert creature.damage_marked == 0
    assert creature.is_attacking is False
    assert creature.is_blocking is False


def test_returned_creature_is_a_new_object_in_combat():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Attacker", 2, 2))
    untap_step(game)
    declare_attackers(game, ["Attacker"])
    assert creature.is_attacking

    move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
    move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)
    assert game.get_battlefield(p1).contains(creature)
    assert creature.is_attacking is False
    assert creature not in game.combat_state.attackers


def test_returned_creature_is_summoning_sick():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature())
    untap_step(game)
    assert creature.summoning_sick is False

    exile(game, creature)
    move_to_zone(game, creature, Zone.EXILE, Zone.BATTLEFIELD)
    assert creature.summoning_sick is True


def test_token_ceases_to_exist_off_the_battlefield():
    game = behavioral_game()
    p1 = game.players[0]
    token = enter_permanent(game, p1, _token())

    destroy(game, token)
    resolve_state_based_actions(game)
    assert not _in_any_zone(game, token)


def test_dies_trigger_sees_last_known_counters():
    game = behavioral_game()
    p1 = game.players[0]
    creature = _with_two_plus_one_counters(game, p1, _creature())
    seen: list[tuple[int, int]] = []

    def _dies(game, event) -> bool:
        if event.creature is not creature:
            return False
        seen.append((event.last_known.counters.get("+1/+1", 0), event.last_known.power))
        return True

    game.trigger_manager.register(TriggerRegistration(
        event_type=CreatureDiesTriggeredEvent, condition=_dies,
        effect=lambda game: None, source=creature, controller=p1,
    ))
    destroy(game, creature)
    assert seen == [(2, 3)]


def test_leaves_trigger_effect_uses_last_known_information():
    from engine.last_known import last_known_info

    game = behavioral_game()
    p1 = game.players[0]
    creature = _with_two_plus_one_counters(game, p1, _creature())
    resolved: list[int] = []

    def _effect(game) -> None:
        resolved.append(last_known_info(game, creature).power)

    game.trigger_manager.register(TriggerRegistration(
        event_type=LeavesBattlefieldTriggeredEvent,
        condition=lambda game, event: event.permanent is creature,
        effect=_effect, source=creature, controller=p1,
    ))
    move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
    resolve_stack(game)
    assert resolved == [3]
    assert creature.power == 1


def test_token_dies_trigger_fires_with_last_known_information():
    game = behavioral_game()
    p1 = game.players[0]
    token = _with_two_plus_one_counters(game, p1, _token())
    seen = []

    def _dies(game, event) -> bool:
        if event.creature is not token:
            return False
        seen.append(event.last_known)
        return True

    game.trigger_manager.register(TriggerRegistration(
        event_type=CreatureDiesTriggeredEvent, condition=_dies,
        effect=lambda game: None, source=token, controller=p1,
    ))
    destroy(game, token)
    resolve_state_based_actions(game)
    assert len(seen) == 1
    assert seen[0].is_token is True
    assert seen[0].counters.get("+1/+1") == 2
    assert seen[0].power == 3
    assert not _in_any_zone(game, token)


def _pump(game, source, creatures, amount=3):
    """A resolved "creatures get +amount/+0 until end of turn" locked onto
    *creatures* (rule 611.2c)."""
    affected = list(creatures)

    def _apply(game) -> None:
        for creature in affected:
            creature.modified_power += amount

    return game.effect_manager.add(ContinuousEffect(
        source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT,
        apply=_apply, duration=DURATION_END_OF_TURN, bound_to=affected,
    ))


def test_effect_locked_onto_a_creature_ends_when_it_leaves():
    game = behavioral_game()
    p1 = game.players[0]
    exiled = enter_permanent(game, p1, _creature("Exiled", 2, 2))
    killed = enter_permanent(game, p1, _creature("Killed", 2, 2))
    _pump(game, _creature("Spell"), [exiled])
    _pump(game, _creature("Spell"), [killed])
    game.effect_manager.apply_all(game)
    assert (exiled.power, killed.power) == (5, 5)

    exile(game, exiled)
    move_to_zone(game, exiled, Zone.EXILE, Zone.BATTLEFIELD)
    destroy(game, killed)
    move_to_zone(game, killed, Zone.GRAVEYARD, Zone.BATTLEFIELD)
    game.effect_manager.apply_all(game)
    assert (exiled.power, killed.power) == (2, 2)


def test_effect_over_several_creatures_keeps_affecting_the_ones_that_stay():
    game = behavioral_game()
    p1 = game.players[0]
    leaves = enter_permanent(game, p1, _creature("Leaves", 2, 2))
    stays = enter_permanent(game, p1, _creature("Stays", 2, 2))
    _pump(game, _creature("Spell"), [leaves, stays])

    move_to_zone(game, leaves, Zone.BATTLEFIELD, Zone.HAND)
    move_to_zone(game, leaves, Zone.HAND, Zone.BATTLEFIELD)
    game.effect_manager.apply_all(game)
    assert leaves.power == 2
    assert stays.power == 5


def test_static_effect_applies_to_a_returned_permanent():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Follower", 2, 2))
    lord = enter_permanent(game, p1, _creature("Lord", 1, 1))

    def _anthem(game) -> None:
        for obj in game.get_battlefield(p1).get_all():
            if obj is not lord:
                obj.modified_power += 1

    game.effect_manager.add(ContinuousEffect(
        source=lord, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT,
        apply=_anthem, duration=DURATION_PERMANENT,
    ))
    exile(game, creature)
    move_to_zone(game, creature, Zone.EXILE, Zone.BATTLEFIELD)
    game.effect_manager.apply_all(game)
    assert creature.power == 3


def test_locked_effect_still_ends_at_cleanup():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Pumped", 2, 2))
    _pump(game, _creature("Spell"), [creature])
    game.effect_manager.apply_all(game)
    assert creature.power == 5

    from engine.turn import cleanup_mechanical

    cleanup_mechanical(game)
    assert creature.power == 2


class _SacrificeForLife(Artifact):
    """Sacrifice this artifact: you gain 1 life."""

    def get_activated_abilities(self):
        def _cost(game, source) -> bool:
            sacrifice(game, source.controller, source)
            return True

        def _effect(game, controller) -> None:
            gain_life(game, controller, 1)

        return [ActivatedAbility(cost=_cost, effect=_effect)]


def test_ability_of_a_sacrificed_source_resolves_for_the_player_who_activated_it():
    """The source is sacrificed as a cost and becomes a new object whose
    controller is its owner (400.7, 108.4a); "you" is still the player who
    activated the ability (602.2)."""
    game = behavioral_game()
    activator, owner = game.players
    artifact = enter_permanent(game, activator, _SacrificeForLife(name="Borrowed Artifact"))
    artifact.owner = owner  # an artifact the activator does not own
    activate_card_ability(game, activator, artifact)
    assert game.get_graveyard(owner).contains(artifact)
    resolve_stack(game)
    assert (activator.life, owner.life) == (21, 20)
