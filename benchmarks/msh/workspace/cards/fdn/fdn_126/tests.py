"""Reference test for FDN 126 — Zimone, Paradox Sculptor.

The activated ability doubles counters on *up to two* target creatures/artifacts
— each pick is declinable (`choose_object(optional=True)`), so it works with
one, two, or zero chosen permanents.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_126.card_impl import ZimoneParadoxSculptor
from engine.abilities import clear_loyalty_tracking
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.game import add_counter
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


@pytest.fixture(autouse=True)
def _reset():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


class TestZimoneProperties:
    def test_static_data(self):
        z = ZimoneParadoxSculptor(owner=None)
        assert z.name == "Zimone, Paradox Sculptor"
        assert z.mana_cost == ManaCost.parse("{2}{G}{U}")

    def test_has_activated_ability(self):
        z = ZimoneParadoxSculptor(owner=None)
        assert len(z.get_activated_abilities()) == 1


class TestZimoneDoubleCounters:
    def test_doubles_a_creatures_counters(self):
        game = create_game()
        p1 = game.players[0]
        zim = ZimoneParadoxSculptor(owner=p1, controller=p1)
        ally = Creature(name="Ally", base_power=1, base_toughness=1,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[zim, ally],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})
        add_counter(game, ally, "+1/+1", 2)
        assert ally.plus_one_counters == 2
        game.phase = Phase.PRECOMBAT_MAIN

        inst = game.refs.instance_id(ally, Zone.BATTLEFIELD.value)
        p1.start_intent("zim", Intent(
            pattern=GameRef(card=frozenset({("name", "Zimone, Paradox Sculptor")})),
            preferences=(Decision.obj(instance=inst),),
        ))
        try:
            activate_card_ability(game, p1, zim)
            resolve_stack(game)
        finally:
            p1.end_intent("zim")
        game.effect_manager.apply_all(game)
        assert ally.plus_one_counters == 4          # 2 doubled → 4
        assert zim.is_tapped                         # {T} paid
