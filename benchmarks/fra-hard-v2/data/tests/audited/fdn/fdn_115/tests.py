"""Audited tests for FDN 115 — Alesha, Who Laughs at Fate.

"Whenever Alesha attacks, put a +1/+1 counter on it. Raid — At the beginning
of your end step, if you attacked this turn, return target creature card with
mana value less than or equal to Alesha's power from your graveyard to the
battlefield." Alesha's power is read when the raid ability resolves: from
Alesha while it remains on the battlefield, otherwise as it last existed there
(rule 608.2h).
"""

from __future__ import annotations

from cards.fdn.fdn_115.card_impl import AleshaWhoLaughsAtFate
from engine.card import Creature
from engine.game import add_counter, destroy
from engine.turn import untap_step
from engine.types import ManaCost, Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
)


def _raid_pending():
    """Alesha with two +1/+1 counters attacks (its attack trigger makes it a
    5/5), and its raid trigger is pending at the end step with a mana value 4
    creature card in the graveyard."""
    game = behavioral_game()
    player = game.players[0]
    alesha = enter_permanent(game, player, AleshaWhoLaughsAtFate())
    add_counter(game, alesha, "+1/+1", 2)
    returned = Creature(
        name="Mana value 4", mana_cost=ManaCost(generic=4), base_power=1, base_toughness=1, owner=player,
    )
    game.get_graveyard(player).add(returned)
    untap_step(game)
    prefer(player, object_preference(game, returned))
    declare_attackers(game, [alesha])
    resolve_stack(game)
    assert alesha.power == 5
    declare_blockers(game, {})
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    return game, player, alesha, returned


class TestAleshaRaid:
    def test_returns_a_creature_card_with_mana_value_up_to_its_power(self) -> None:
        game, player, _alesha, returned = _raid_pending()
        resolve_stack(game)
        assert game.get_battlefield(player).contains(returned)

    def test_uses_its_power_as_it_last_existed_if_it_left(self) -> None:
        game, player, alesha, returned = _raid_pending()
        destroy(game, alesha)
        resolve_stack(game)
        assert game.get_battlefield(player).contains(returned)
