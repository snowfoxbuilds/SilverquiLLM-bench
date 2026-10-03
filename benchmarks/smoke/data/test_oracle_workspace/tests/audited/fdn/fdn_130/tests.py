"""Reference test for FDN 130 — Quick-Draw Katana.

During your turn, equipped creature gets +2/+0 and has first strike. The buff
is conditional on the active player, so it appears only on your turn. See
fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_130.card_impl import QuickDrawKatana
from engine.card import Creature, Equipment
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestQuickDrawKatanaProperties:
    def test_static_data(self):
        katana = QuickDrawKatana(owner=None)
        assert katana.name == "Quick-Draw Katana"
        assert katana.mana_cost == ManaCost.parse("{2}")
        assert katana.equip_cost == ManaCost.parse("{2}")
        assert isinstance(katana, Equipment) and katana.is_equipment is True


class TestQuickDrawKatanaBehaviour:
    def test_buff_only_on_controllers_turn(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        katana = QuickDrawKatana(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, katana])
        katana.equip(bear, game)

        # p1 is the active player -> buff active.
        game.active_player_index = 0
        game.effect_manager.apply_all(game)
        assert bear.power == 4  # 2 + 2
        assert Keyword.FIRST_STRIKE in bear.keywords

        # Opponent's turn -> no buff.
        game.active_player_index = 1
        game.effect_manager.apply_all(game)
        assert bear.power == 2
        assert Keyword.FIRST_STRIKE not in bear.keywords
