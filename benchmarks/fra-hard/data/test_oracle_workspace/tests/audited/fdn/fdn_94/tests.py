"""Audited tests for FDN 94 — Slumbering Cerberus.

"This creature doesn't untap during your untap step. Morbid — At the beginning
of each end step, if a creature died this turn, untap this creature." Each
test drives a real death or its absence, then the end step (rules 502.3,
700.4).
"""

from __future__ import annotations

from cards.fdn.fdn_94.card_impl import SlumberingCerberus
from engine.card import Creature
from engine.game import destroy, tap
from engine.turn import untap_step
from engine.types import ManaCost, Phase, Step
from test_utils import advance_game_to_phase, behavioral_game, enter_permanent, resolve_stack


def _tapped_cerberus():
    game = behavioral_game()
    player = game.players[0]
    cerberus = enter_permanent(game, player, SlumberingCerberus())
    tap(game, cerberus)
    return game, player, cerberus


class TestSlumberingCerberusProperties:
    def test_static_data(self):
        card = SlumberingCerberus(owner=None)
        assert card.name == "Slumbering Cerberus"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (4, 2)
        assert "Dog" in card.subtypes


class TestSlumberingCerberusMorbid:
    def test_untaps_when_a_creature_died_this_turn(self):
        game, player, cerberus = _tapped_cerberus()
        victim = enter_permanent(game, player, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert cerberus.is_tapped is False

    def test_stays_tapped_when_no_creature_died(self):
        game, _player, cerberus = _tapped_cerberus()
        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert cerberus.is_tapped is True

        untap_step(game)
        assert cerberus.is_tapped is True
