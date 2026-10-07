"""A permanent that leaves the battlefield becomes a new object (rule 400.7).

It keeps none of its counters (122.2), status (110.5b, 110.5d), combat role
(506.4) or freedom from summoning sickness (302.6), and a token stops existing
(111.7, 704.5d). Abilities that refer to the object as it last existed on the
battlefield read its last-known information instead (603.10a, 608.2h), and an
effect locked onto it by a resolved spell or ability no longer applies to it
(611.2c).
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_187.card_impl import Zombify
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Phase, Side, Step, card, create_game
from test_utils import (
    activate_card_ability,
    behavioral_game,
    enter_permanent,
    resolve_stack,
)

from engine.card import ActivatedAbility, Artifact, Creature
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.events import CreatureDiesTriggeredEvent, LeavesBattlefieldTriggeredEvent
from engine.game import add_counter, destroy, exile, gain_life, sacrifice, tap
from engine.state_based_actions import resolve_state_based_actions
from engine.triggers import TriggerRegistration
from engine.types import Zone
from engine.zones import move_to_zone
from table import Table, life, moves, taps


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


def _tap_and_cast(t, lands, spell, *, choices=(), then=()):
    """Player 0 taps ``lands`` and casts ``spell``, and both players pass."""
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=list(then))


def _bolt_then_zombify(lions):
    """Player 0, in their first main phase, kills their own Savannah Lions
    with Burst Lightning and returns it to the battlefield with Zombify."""
    bolt, zombify, mountain, swamp = card(BurstLightning), card(Zombify), card(Mountain), card(Swamp)
    plains = [card(Plains) for _ in range(3)]
    t = Table(create_game(
        Side(hand=[bolt, zombify], battlefield=[lions, mountain, swamp, *plains]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    ))
    _tap_and_cast(t, [mountain], bolt, choices=[lions],
                  then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    _tap_and_cast(t, [swamp, *plains], zombify, choices=[lions],
                  then=[moves(zombify, Zone.GRAVEYARD), moves(lions, Zone.BATTLEFIELD)])
    return t


def test_card_off_the_battlefield_has_no_status():
    """An attacking Savannah Lions killed in combat is an untapped card in the
    graveyard, and Zombify returns it with none of the damage that killed it."""
    lions, scourge, zombify, swamp = card(SavannahLions), card(BrazenScourge), card(Zombify), card(Swamp)
    plains = [card(Plains) for _ in range(3)]
    t = Table(create_game(
        Side(hand=[zombify], battlefield=[lions, swamp, *plains]),
        Side(battlefield=[scourge]),
        start=(Step.BEGIN_COMBAT, 0),
    ))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, scourge, scoped={scourge: lions})
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.GRAVEYARD)], note="the Lions is in the graveyard untapped")
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    _tap_and_cast(t, [swamp, *plains], zombify, choices=[lions],
                  then=[moves(zombify, Zone.GRAVEYARD), moves(lions, Zone.BATTLEFIELD)])
    t.pass_(0, note="the returned Lions survives: it has no damage marked")
    t.run()


def test_returned_creature_is_a_new_object_in_combat():
    """An attacking Spectral Sailor returned to its owner's hand by Run Away
    Together and cast again is a new object that is not attacking, so only
    the Savannah Lions attacking beside it deals combat damage."""
    sailor, lions, elves = card(SpectralSailor), card(SavannahLions), card(LlanowarElves)
    run_away, islands, plains = card(RunAwayTogether), [card(Island), card(Island)], card(Plains)
    t = Table(create_game(
        Side(hand=[run_away], battlefield=[sailor, lions, *islands, plains]),
        Side(battlefield=[elves]),
        start=(Step.BEGIN_COMBAT, 0),
    ))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, sailor, lions, then=[taps(sailor), taps(lions)])
    _tap_and_cast(t, [islands[0], plains], run_away, choices=[sailor, elves],
                  then=[moves(run_away, Zone.GRAVEYARD), moves(sailor, Zone.HAND), moves(elves, Zone.HAND)])
    _tap_and_cast(t, [islands[1]], sailor, then=[moves(sailor, Zone.BATTLEFIELD)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)], note="only the Lions' 2 damage: the Sailor is not attacking")
    t.run()


def test_returned_creature_is_summoning_sick():
    """A Savannah Lions that dies and returns with Zombify has come under its
    controller's control this turn, so it can't attack."""
    lions = card(SavannahLions)
    t = _bolt_then_zombify(lions)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act_illegal(0, lions, note="the returned Lions is summoning sick")
    t.pass_(0)
    t.pass_(0)
    t.pass_(1)
    t.run()


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


def _pending_power_reader(game, player, source):
    """Register an upkeep trigger on *source* that records "this creature's
    power" when it resolves, and fire it so it is pending."""
    from engine.events import BeginningOfUpkeepTriggeredEvent
    from engine.last_known import as_it_exists
    from engine.stack import battlefield_stint_id

    seen: list[int] = []

    def _effect(game, controller, stint) -> None:
        seen.append(as_it_exists(game, source, stint).power)

    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None, effect=_effect,
        source=source, controller=player,
        capture=lambda game, event, controller: battlefield_stint_id(game, source),
    ))
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    return seen


def test_pending_ability_reads_its_source_as_it_exists_on_resolution():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Source", 1, 1))
    seen = _pending_power_reader(game, p1, creature)
    add_counter(game, creature, "+1/+1", 2)
    resolve_stack(game)
    assert seen == [3]


def test_pending_ability_reads_its_departed_source_from_its_own_stint():
    game = behavioral_game()
    p1 = game.players[0]
    creature = _with_two_plus_one_counters(game, p1, _creature("Source", 1, 1))
    seen = _pending_power_reader(game, p1, creature)
    destroy(game, creature)  # left as a 3/3
    move_to_zone(game, creature, Zone.GRAVEYARD, Zone.BATTLEFIELD)
    add_counter(game, creature, "+1/+1", 5)  # the new object: a 6/6
    destroy(game, creature)
    resolve_stack(game)
    assert seen == [3]
