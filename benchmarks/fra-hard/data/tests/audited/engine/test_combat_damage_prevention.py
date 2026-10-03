"""Combat damage that would be dealt to a permanent whose combat damage is
prevented this turn is not dealt (rules 615.1, 510.2)."""

from __future__ import annotations

from engine.card import Creature
from engine.combat import combat_damage_step
from engine.turn import untap_step
from engine.types import Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
)


def _protected_attacker_blocked_by_a_four_four():
    game = behavioral_game()
    player, opponent = game.players
    attacker = enter_permanent(game, player, Creature(name="Protected", base_power=3, base_toughness=3))
    blocker = enter_permanent(game, opponent, Creature(name="Big Blocker", base_power=4, base_toughness=4))
    untap_step(game)
    attacker.combat_damage_prevented = True  # as a resolved "prevent all combat damage ... this turn"
    declare_attackers(game, ["Protected"])
    declare_blockers(game, {"Protected": ["Big Blocker"]})
    combat_damage_step(game)
    return game, player, opponent, attacker, blocker


def test_prevented_creature_survives_a_lethal_block():
    game, player, _opponent, attacker, _blocker = _protected_attacker_blocked_by_a_four_four()
    assert game.get_battlefield(player).contains(attacker)
    assert attacker.damage_marked == 0


def test_prevented_creature_still_deals_its_damage():
    game, _player, opponent, _attacker, blocker = _protected_attacker_blocked_by_a_four_four()
    assert game.get_battlefield(opponent).contains(blocker)
    assert blocker.damage_marked == 3


def test_prevention_ends_at_cleanup():
    game, _player, _opponent, attacker, _blocker = _protected_attacker_blocked_by_a_four_four()
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert not getattr(attacker, "combat_damage_prevented", False)
