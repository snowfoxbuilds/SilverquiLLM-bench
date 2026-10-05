import pytest
from card_impl import AncestralCraving, BloodlineRecollector
from engine.card import Artifact, Creature, Instant
from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
from engine.decisions import Decision, satisfies
from engine.game import exile, sacrifice
from engine.queries import is_priority_query
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    ScriptEntryError,
    act,
    act_illegal,
    advance_game_to_phase,
    branch,
    behavioral_game,
    cast_card,
    enter_permanent,
    offered_actions,
    resolve_stack,
    take_action,
)


def arrange(deaths=3, opponent=False):
    game = behavioral_game()
    player = game.players[0]
    source = enter_permanent(game, player, BloodlineRecollector())
    owner = game.players[1] if opponent else player
    for i in range(deaths):
        victim = enter_permanent(game, owner, Creature(name=f"Victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, owner, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    return game, player, source


def craving(game, seat=0, target_seat=0, illegal=False):
    """Cast Ancestral Craving, whether the engine offers the inset spell at once
    or offers its prepared card and then asks which spell to cast.

    The offered actions only enumerate what could be chosen, never what is
    legal: each Ancestral Craving or Bloodline Recollector the player is offered
    gets its own branch, choosing that option at priority and Ancestral Craving
    if a face is asked for, so an engine that offers a consumed or unprepared
    one and rejects it is retried with the next.
    """
    candidates = (Decision.obj(printed=AncestralCraving), Decision.obj(printed=BloodlineRecollector))
    options = [option for option in offered_actions(game, seat)
               if any(satisfies(option, candidate) for candidate in candidates)]
    branches = [branch(AncestralCraving, per_query={is_priority_query: [option]}) for option in options]
    entry = act_illegal if illegal else act
    return entry(branches=branches or [[AncestralCraving]],
                 choices=(Decision.player(seat=target_seat),))


def cast_craving(game, seat=0, target_seat=0):
    take_action(game, seat, craving(game, seat, target_seat))


def castable_cravings(game, seat=0, limit=3):
    """How many prepared Ancestral Cravings the player can cast now, given {B}
    for each; the ones cast are left on the stack."""
    player = game.players[seat]
    for count in range(limit):
        player.mana_pool.add(ManaType.BLACK, 1)
        try:
            take_action(game, seat, craving(game, seat, seat))
        except ScriptEntryError:
            return count
    return limit


@pytest.mark.parametrize("deaths", [0, 1, 2])
def test_fewer_than_three_deaths_does_not_prepare(deaths):
    game, _player, _source = arrange(deaths)
    assert castable_cravings(game) == 0


@pytest.mark.parametrize("opponent", [False, True])
def test_three_deaths_prepares_even_if_opponents_creatures(opponent):
    game, player, source = arrange(opponent=opponent)
    assert castable_cravings(game) == 1
    assert game.get_battlefield(player).contains(source)


def test_prepared_spell_draws_and_loses_life_and_unprepares():
    game, player, source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 3 and player.life == 17
    assert castable_cravings(game) == 0
    assert game.get_battlefield(player).contains(source)


def test_can_target_opponent():
    game, player, _source = arrange()
    opponent = game.players[1]
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game, target_seat=1)
    resolve_stack(game)
    assert opponent.life == 17 and len(game.get_hand(opponent).get_all()) == 3
    assert player.life == 20


def test_prepared_copy_still_requires_black_mana():
    game, player, _source = arrange()
    take_action(game, 0, craving(game, illegal=True))
    assert player.life == 20 and castable_cravings(game) == 1


def test_prepared_copy_disappears_when_permanent_leaves():
    game, _player, source = arrange()
    exile(game, source)
    resolve_stack(game)
    assert castable_cravings(game) == 0


def test_pending_spell_survives_source_leaving():
    game, player, source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game)
    exile(game, source)
    resolve_stack(game)
    assert player.life == 17 and len(game.get_hand(player).get_all()) == 3


def test_blink_does_not_preserve_preparation():
    game, player, source = arrange()
    move_to_zone(game, source, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, source, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert castable_cravings(game) == 0
    assert player.life == 20


def test_multiple_prepare_events_do_not_accumulate_copies():
    game, player, _source = arrange()
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"New victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 1


def test_noncreature_deaths_do_not_prepare():
    game = behavioral_game()
    player = game.players[0]
    enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Artifact(name=f"Relic {i}"))
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 0


def test_deaths_before_recollector_entered_are_counted():
    game = behavioral_game()
    player = game.players[0]
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, player, victim)
    enter_permanent(game, player, BloodlineRecollector())
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 1


def test_old_turn_deaths_do_not_prepare_next_turn():
    game, player, _source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 0


class Steal(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Steal response", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        player = self.controller

        def apply(state):
            for previous in state.players:
                if state.get_battlefield(previous).contains(self.target):
                    if previous is not player:
                        state.get_battlefield(previous).remove(self.target)
                        state.get_battlefield(player).add(self.target)
                    self.target.controller = player
                    break

        game.effect_manager.add(ContinuousEffect(self, Layer.CONTROL, apply=apply,
                                                duration=DURATION_END_OF_TURN))


def test_control_change_transfers_cast_permission_without_recreating_copy():
    game, player, source = arrange()
    opponent = game.players[1]
    cast_card(game, opponent, Steal(source, owner=opponent))
    player.mana_pool.add(ManaType.BLACK, 1)
    take_action(game, 0, craving(game, illegal=True))
    opponent.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game, seat=1, target_seat=0)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 3
    assert castable_cravings(game, 0) == castable_cravings(game, 1) == 0


def test_creatures_exiled_instead_of_dying_do_not_prepare():
    game = behavioral_game()
    player = game.players[0]
    enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Exiled {i}", base_power=1, base_toughness=1))
        exile(game, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 0


def test_token_creature_deaths_count():
    game = behavioral_game()
    player = game.players[0]
    enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Token {i}", base_power=1, base_toughness=1))
        victim.is_token = True
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 1


def test_preparation_is_consumed_on_cast_before_resolution():
    game, player, _ = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game)
    assert player.life == 20 and castable_cravings(game) == 0
    resolve_stack(game)
    assert player.life == 17


def test_leaving_before_prepare_trigger_resolves_does_not_prepare():
    game = behavioral_game()
    player = game.players[0]
    source = enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        sacrifice(game, player, enter_permanent(game, player, Creature(name=f"Victim {i}", base_power=1, base_toughness=1)))
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    exile(game, source)
    resolve_stack(game)
    assert castable_cravings(game) == 0


def test_two_recollectors_prepare_independently():
    game = behavioral_game()
    player = game.players[0]
    sources = [enter_permanent(game, player, BloodlineRecollector()) for _ in range(2)]
    for i in range(3):
        sacrifice(game, player, enter_permanent(game, player, Creature(name=f"Victim {i}", base_power=1, base_toughness=1)))
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert castable_cravings(game) == 2
    resolve_stack(game)
    assert player.life == 14 and len(game.get_hand(player).get_all()) == 6
    assert castable_cravings(game) == 0
    assert all(game.get_battlefield(player).contains(source) for source in sources)


def test_countered_prepared_spell_still_consumes_preparation():
    from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse

    game, player, source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_craving(game)
    opponent = game.players[1]
    opponent.mana_pool.add(ManaType.BLUE, 1)
    cast_card(game, opponent, AnOfferYouCantRefuse())
    assert player.life == 20 and not game.get_hand(player).get_all()
    assert castable_cravings(game) == 0
    assert game.get_battlefield(player).contains(source)
