"""Reference test for FDN 94 — Slumbering Cerberus.

Regression guard for the ``is_tapped`` attribute fix: the Morbid end-step
trigger must untap the creature by clearing the engine field ``is_tapped``
(not a stray ``.tapped``). Drives the trigger through the real
register -> fire_event -> resolve_stack path.
"""

from __future__ import annotations

from cards.fdn.fdn_94.card_impl import SlumberingCerberus
from engine.events import EndStepTriggeredEvent
from engine.types import ManaCost
from test_utils import create_game, resolve_stack, set_board_state


def _setup():
    game = create_game()
    p1 = game.players[0]
    cerb = SlumberingCerberus(owner=p1, controller=p1)
    set_board_state(game, 0, battlefield=[cerb])
    cerb.register_triggers(game)
    cerb.is_tapped = True  # cerberus is currently tapped
    return game, p1, cerb


class TestSlumberingCerberusProperties:
    def test_static_data(self):
        c = SlumberingCerberus(owner=None)
        assert c.name == "Slumbering Cerberus"
        assert c.mana_cost == ManaCost.parse("{1}{R}")
        assert (c.base_power, c.base_toughness) == (4, 2)
        assert "Dog" in c.subtypes
        assert c.skip_untap is True  # doesn't untap normally


class TestSlumberingCerberusMorbid:
    def test_untaps_when_a_creature_died_this_turn(self):
        game, p1, cerb = _setup()
        game.creature_died_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        resolve_stack(game)
        assert cerb.is_tapped is False  # Morbid untapped it

    def test_stays_tapped_when_no_creature_died(self):
        game, p1, cerb = _setup()
        game.creature_died_this_turn = False
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        resolve_stack(game)
        assert cerb.is_tapped is True  # condition false: no untap
