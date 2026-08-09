"""Reference test for FDN 253 — Goldvein Pick.

Equipped creature gets +1/+1; whenever it deals combat damage to a player,
create a Treasure token. See fdn_129/tests.py for the canonical shape.
"""

from __future__ import annotations

from cards.fdn.fdn_253.card_impl import GoldveinPick
from engine.card import Creature, Equipment
from engine.events import DealsDamageTriggeredEvent
from engine.stack import priority_loop
from engine.types import ManaCost
from test_utils import create_game, set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestGoldveinPickProperties:
    def test_static_data(self):
        pick = GoldveinPick(owner=None)
        assert pick.name == "Goldvein Pick"
        assert pick.mana_cost == ManaCost.parse("{2}")
        assert pick.equip_cost == ManaCost.parse("{1}")
        assert isinstance(pick, Equipment) and pick.is_equipment is True


class TestGoldveinPickBehaviour:
    def test_grants_plus_one_plus_one(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        pick = GoldveinPick(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, pick])
        pick.equip(bear, game)
        assert (bear.power, bear.toughness) == (3, 3)

    def test_combat_damage_to_player_makes_treasure(self):
        game = create_game()
        p1, p2 = game.players
        bear = _bear(p1)
        pick = GoldveinPick(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, pick])
        pick.register_triggers(game)
        pick.equip(bear, game)

        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(
            source=bear, target=p2, amount=3, is_combat=True,
        ))
        priority_loop(game)

        treasures = [o for o in game.get_battlefield(p1).get_all()
                     if getattr(o, "name", "") == "Treasure"]
        assert len(treasures) == 1
        assert "Treasure" in treasures[0].subtypes
