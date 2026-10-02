"""A permanent that leaves the battlefield becomes a new object (rule 400.7).

It keeps none of its counters (122.2), status (110.5b, 110.5d), combat role
(506.4) or freedom from summoning sickness (302.6), and a token stops existing
(111.7, 704.5d). Abilities that refer to the object as it last existed on the
battlefield read its last-known information instead (603.10a, 608.2h).
"""

from __future__ import annotations

from engine.card import Creature
from engine.events import CreatureDiesTriggeredEvent, LeavesBattlefieldTriggeredEvent
from engine.game import add_counter, deal_damage, destroy, exile, tap
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import TriggerRegistration
from engine.turn import untap_step
from engine.types import Zone
from engine.zones import move_to_zone
from test_utils import behavioral_game, declare_attackers, enter_permanent, resolve_stack


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
