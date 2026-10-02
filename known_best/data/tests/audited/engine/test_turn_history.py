"""Per-turn history the engine keeps for abilities to read: whether a player
attacked this turn (raid, rule 508.1) and whether a creature died this turn
(morbid, 700.4), plus permanents that don't untap during the untap step
(502.3)."""

from __future__ import annotations

from engine.card import Creature
from engine.game import destroy, tap
from engine.turn import untap_step
from engine.types import Phase, Step
from test_utils import advance_game_to_phase, behavioral_game, declare_attackers, enter_permanent


class _DoesNotUntap(Creature):
    skip_untap = True


def _next_turn(game) -> None:
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)


def test_declaring_an_attacker_records_attacked_this_turn():
    game = behavioral_game()
    attacker_player, opponent = game.players
    enter_permanent(game, attacker_player, Creature(name="Raider", base_power=2, base_toughness=2))
    untap_step(game)
    assert not attacker_player.attacked_this_turn

    declare_attackers(game, ["Raider"])
    assert attacker_player.attacked_this_turn is True
    assert opponent.attacked_this_turn is False

    _next_turn(game)
    assert attacker_player.attacked_this_turn is False


def test_creature_dying_records_creature_died_this_turn():
    game = behavioral_game()
    player = game.players[0]
    creature = enter_permanent(game, player, Creature(name="Victim", base_power=1, base_toughness=1))
    assert not game.creature_died_this_turn

    destroy(game, creature)
    assert game.creature_died_this_turn is True

    _next_turn(game)
    assert game.creature_died_this_turn is False


def test_permanent_that_does_not_untap_stays_tapped():
    game = behavioral_game()
    player = game.players[0]
    stays = enter_permanent(game, player, _DoesNotUntap(name="Stays Tapped", base_power=1, base_toughness=1))
    untaps = enter_permanent(game, player, Creature(name="Untaps", base_power=1, base_toughness=1))
    tap(game, stays)
    tap(game, untaps)

    untap_step(game)
    assert stays.is_tapped is True
    assert untaps.is_tapped is False
