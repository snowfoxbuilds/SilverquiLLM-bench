"""Reference test for FDN 258 — Swiftfoot Boots.

Equipped creature has hexproof and haste. See fdn_129/tests.py for the
canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_258.card_impl import SwiftfootBoots
from engine.card import Creature, Equipment
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestSwiftfootBootsProperties:
    def test_static_data(self):
        boots = SwiftfootBoots(owner=None)
        assert boots.name == "Swiftfoot Boots"
        assert boots.mana_cost == ManaCost.parse("{2}")
        assert boots.equip_cost == ManaCost.parse("{1}")
        assert isinstance(boots, Equipment) and boots.is_equipment is True


class TestSwiftfootBootsBehaviour:
    def test_grants_hexproof_and_haste(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        boots = SwiftfootBoots(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, boots])
        boots.equip(bear, game)
        assert Keyword.HEXPROOF in bear.keywords
        assert Keyword.HASTE in bear.keywords
        boots.detach(game)
        assert Keyword.HEXPROOF not in bear.keywords
        assert Keyword.HASTE not in bear.keywords
