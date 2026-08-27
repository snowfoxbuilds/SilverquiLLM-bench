"""Reference test for FDN 12 — Felidar Savior.

"put a +1/+1 counter on each of UP TO TWO other target creatures you control"
→ two optional requirements. The ETB stays castable with fewer than two (or
zero) other creatures, and the engine picks two *distinct* creatures.
"""

from __future__ import annotations

from cards.fdn.fdn_12.card_impl import FelidarSavior
from engine.card import Creature
from engine.types import ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _ally(p, name):
    return Creature(name=name, base_power=1, base_toughness=1, owner=p, controller=p)


class TestFelidarSaviorProperties:
    def test_static_data(self):
        fs = FelidarSavior(owner=None)
        assert fs.name == "Felidar Savior"
        assert fs.mana_cost == ManaCost.parse("{3}{W}")

    def test_both_target_specs_optional(self):
        fs = FelidarSavior(owner=None)
        specs = fs.get_targets(create_game())
        assert len(specs) == 2
        assert all(s.optional for s in specs)


class TestFelidarSaviorETB:
    def test_castable_with_no_other_creatures(self):
        """No other creatures you control: the ETB still casts and simply grants
        no counters (both optional targets skipped)."""
        game = create_game()
        p1 = game.players[0]
        fs = FelidarSavior(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[fs], mana={ManaType.WHITE: 4})
        cast_spell(game, 0, "Felidar Savior")
        assert game.get_battlefield(p1).contains(fs)   # it resolved and entered

    def test_one_other_creature_gets_a_counter(self):
        game = create_game()
        p1 = game.players[0]
        ally = _ally(p1, "Ally")
        fs = FelidarSavior(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ally], hand=[fs],
                        mana={ManaType.WHITE: 4})
        cast_spell(game, 0, "Felidar Savior", targets=[ally])
        assert ally.plus_one_counters == 1

    def test_two_other_creatures_both_get_distinct_counters(self):
        game = create_game()
        p1 = game.players[0]
        a, b = _ally(p1, "A"), _ally(p1, "B")
        fs = FelidarSavior(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[a, b], hand=[fs],
                        mana={ManaType.WHITE: 4})
        cast_spell(game, 0, "Felidar Savior", targets=[a, b])
        assert a.plus_one_counters == 1 and b.plus_one_counters == 1
