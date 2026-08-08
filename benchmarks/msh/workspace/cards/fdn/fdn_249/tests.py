"""Reference test for FDN 249 — Adventuring Gear.

No static buff; a landfall trigger gives the equipped creature +2/+2 until end
of turn. See fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_249.card_impl import AdventuringGear
from engine.card import Creature, Equipment, Land
from engine.stack import priority_loop
from engine.turn import cleanup_mechanical
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestAdventuringGearProperties:
    def test_static_data(self):
        gear = AdventuringGear(owner=None)
        assert gear.name == "Adventuring Gear"
        assert gear.mana_cost == ManaCost.parse("{1}")
        assert gear.equip_cost == ManaCost.parse("{1}")
        assert isinstance(gear, Equipment) and gear.is_equipment is True


class TestAdventuringGearBehaviour:
    def test_no_static_buff(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        gear = AdventuringGear(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, gear])
        gear.equip(bear, game)
        assert (bear.power, bear.toughness) == (2, 2)

    def test_landfall_pumps_until_end_of_turn(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        gear = AdventuringGear(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, gear])
        gear.register_triggers(game)
        gear.equip(bear, game)

        land = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[land])
        move_to_zone(game, land, Zone.HAND, Zone.BATTLEFIELD)
        priority_loop(game)  # resolve the landfall trigger
        game.effect_manager.apply_all(game)
        assert (bear.power, bear.toughness) == (4, 4)

        cleanup_mechanical(game)  # the +2/+2 is until end of turn
        assert (bear.power, bear.toughness) == (2, 2)
