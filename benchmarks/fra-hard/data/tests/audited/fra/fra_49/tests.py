import pytest
from card_impl import BloodlineRecollector
from engine.card import Artifact, Creature, Instant
from engine.casting import CastingError, cast_spell
from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
from engine.decisions import Decision
from engine.game import exile, sacrifice
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    prefer,
    resolve_stack,
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


def copies(player):
    return [card for card in player.zones[Zone.EXILE].get_all() if card.name == "Ancestral Craving"]


@pytest.mark.parametrize("deaths", [0, 1, 2])
def test_fewer_than_three_deaths_does_not_prepare(deaths):
    _game, player, _source = arrange(deaths)
    assert not copies(player)


@pytest.mark.parametrize("opponent", [False, True])
def test_three_deaths_prepares_even_if_opponents_creatures(opponent):
    game, player, source = arrange(opponent=opponent)
    assert len(copies(player)) == 1
    assert game.get_battlefield(player).contains(source)


def test_prepared_spell_draws_and_loses_life_and_unprepares():
    game, player, source = arrange()
    spell = copies(player)[0]
    player.mana_pool.add(ManaType.BLACK, 1)
    prefer(player, Decision.player(seat=0))
    cast_spell(game, player, spell)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 3 and player.life == 17
    assert not copies(player)
    assert all(not player.zones[zone].contains(spell) for zone in Zone)
    assert game.get_battlefield(player).contains(source)


def test_can_target_opponent():
    game, player, _source = arrange()
    opponent = game.players[1]
    player.mana_pool.add(ManaType.BLACK, 1)
    prefer(player, Decision.player(seat=1))
    cast_spell(game, player, copies(player)[0])
    resolve_stack(game)
    assert opponent.life == 17 and len(game.get_hand(opponent).get_all()) == 3
    assert player.life == 20


def test_prepared_copy_still_requires_black_mana():
    game, player, _source = arrange()
    with pytest.raises(CastingError):
        cast_spell(game, player, copies(player)[0])
    assert len(copies(player)) == 1 and player.life == 20


def test_prepared_copy_disappears_when_permanent_leaves():
    game, player, source = arrange()
    exile(game, source)
    resolve_stack(game)
    assert not copies(player)


def test_pending_spell_survives_source_leaving():
    game, player, source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_spell(game, player, copies(player)[0])
    exile(game, source)
    resolve_stack(game)
    assert player.life == 17 and len(game.get_hand(player).get_all()) == 3


def test_blink_does_not_preserve_preparation():
    game, player, source = arrange()
    old_spell = copies(player)[0]
    move_to_zone(game, source, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, source, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert not copies(player)
    player.mana_pool.add(ManaType.BLACK)
    with pytest.raises(CastingError):
        cast_spell(game, player, old_spell)


def test_multiple_prepare_events_do_not_accumulate_copies():
    game, player, _source = arrange()
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"New victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert len(copies(player)) == 1


def test_noncreature_deaths_do_not_prepare():
    game = behavioral_game()
    player = game.players[0]
    enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Artifact(name=f"Relic {i}"))
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert not copies(player)


def test_deaths_before_recollector_entered_are_counted():
    game = behavioral_game()
    player = game.players[0]
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, player, victim)
    enter_permanent(game, player, BloodlineRecollector())
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert len(copies(player)) == 1


def test_old_turn_deaths_do_not_prepare_next_turn():
    game, player, _source = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_spell(game, player, copies(player)[0])
    resolve_stack(game)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert not copies(player)


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
    spell = copies(player)[0]
    opponent = game.players[1]
    cast_card(game, opponent, Steal(source, owner=opponent))
    opponent.mana_pool.add(ManaType.BLACK, 1)
    cast_spell(game, opponent, spell)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 3
    assert not copies(player) and not copies(opponent)


def test_creatures_exiled_instead_of_dying_do_not_prepare():
    game = behavioral_game()
    player = game.players[0]
    _source = enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Exiled {i}", base_power=1, base_toughness=1))
        exile(game, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert not copies(player)


def test_token_creature_deaths_count():
    game = behavioral_game()
    player = game.players[0]
    _source = enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        victim = enter_permanent(game, player, Creature(name=f"Token {i}", base_power=1, base_toughness=1))
        victim.is_token = True
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert len(copies(player)) == 1


def test_preparation_is_consumed_on_cast_before_resolution():
    game, player, _ = arrange()
    player.mana_pool.add(ManaType.BLACK, 1)
    spell = copies(player)[0]
    cast_spell(game, player, spell)
    assert not copies(player) and player.life == 20
    player.mana_pool.add(ManaType.BLACK, 1)
    with pytest.raises(CastingError):
        cast_spell(game, player, spell)
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
    assert not copies(player)


def test_two_recollectors_prepare_independently():
    game = behavioral_game()
    player = game.players[0]
    _source = enter_permanent(game, player, BloodlineRecollector())
    enter_permanent(game, player, BloodlineRecollector())
    for i in range(3):
        sacrifice(game, player, enter_permanent(game, player, Creature(name=f"Victim {i}", base_power=1, base_toughness=1)))
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert len(copies(player)) == 2
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_spell(game, player, copies(player)[0])
    resolve_stack(game)
    assert len(copies(player)) == 1


def test_countered_prepared_spell_still_consumes_preparation():
    from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse

    game, player, source = arrange()
    spell = copies(player)[0]
    player.mana_pool.add(ManaType.BLACK, 1)
    cast_spell(game, player, spell)
    opponent = game.players[1]
    opponent.mana_pool.add(ManaType.BLUE, 1)
    cast_card(game, opponent, AnOfferYouCantRefuse())
    assert player.life == 20 and not game.get_hand(player).get_all()
    assert not copies(player)
    assert all(not player.zones[zone].contains(spell) for zone in Zone)
    assert game.get_battlefield(player).contains(source)
