"""Audited tests for FDN 117 — Ashroot Animist.

"Whenever this creature attacks, another target creature you control gains
trample and gets +X/+X until end of turn, where X is this creature's power."
X is read when the ability resolves: from the Animist while it remains on the
battlefield, otherwise as it last existed there (rule 608.2h).
"""

from __future__ import annotations

from cards.fdn.fdn_117.card_impl import AshrootAnimist
from engine.card import Creature
from engine.game import add_counter, destroy
from engine.turn import untap_step
from engine.types import Keyword, Zone
from engine.zones import move_to_zone
from test_utils import (
    behavioral_game,
    declare_attackers,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
)


def _attacking(counters: int = 0):
    """The Animist (4/4, plus *counters* +1/+1 counters) attacks; its trigger
    is pending. Returns the game, the Animist and a 2/2 ally."""
    game = behavioral_game()
    player = game.players[0]
    animist = enter_permanent(game, player, AshrootAnimist())
    ally = enter_permanent(game, player, Creature(name="Ally", base_power=2, base_toughness=2))
    if counters:
        add_counter(game, animist, "+1/+1", counters)
    untap_step(game)
    prefer(player, object_preference(game, ally))
    declare_attackers(game, [animist.name])
    return game, animist, ally


class TestAshrootAnimistAttack:
    def test_another_creature_gets_plus_x_and_trample(self) -> None:
        game, _animist, ally = _attacking()
        resolve_stack(game)
        assert (ally.power, ally.toughness) == (6, 6)
        assert Keyword.TRAMPLE in ally.keywords

    def test_power_gained_after_triggering_counts_while_it_stays(self) -> None:
        game, animist, ally = _attacking()
        add_counter(game, animist, "+1/+1", 3)
        resolve_stack(game)
        assert (ally.power, ally.toughness) == (9, 9)

    def test_uses_its_power_as_it_last_existed_if_it_left(self) -> None:
        game, animist, ally = _attacking(counters=3)
        destroy(game, animist)
        resolve_stack(game)
        assert (ally.power, ally.toughness) == (9, 9)

    def test_a_later_return_and_departure_do_not_change_the_pending_power(self) -> None:
        game, animist, ally = _attacking(counters=3)  # power 7 as it attacked
        destroy(game, animist)
        move_to_zone(game, animist, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        add_counter(game, animist, "+1/+1", 5)  # the new object: power 9
        destroy(game, animist)
        resolve_stack(game)
        assert (ally.power, ally.toughness) == (9, 9)
