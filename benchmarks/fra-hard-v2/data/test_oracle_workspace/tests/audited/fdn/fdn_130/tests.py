"""Reference test for FDN 130 — Quick-Draw Katana.

During your turn, equipped creature gets +2/+0 and has first strike. The buff
is conditional on the active player, so it appears only on your turn. See
fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_21.card_impl import PridefulParent
from cards.fdn.fdn_130.card_impl import QuickDrawKatana, QuickDrawKatanaAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import Equipment, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, first_strike_damage, life, moves, off_stack, on_stack, taps


class TestQuickDrawKatanaProperties:
    def test_static_data(self):
        katana = QuickDrawKatana(owner=None)
        assert printed_class(katana) is QuickDrawKatana
        assert katana.mana_cost == ManaCost.parse("{2}")
        assert katana.equip_cost == ManaCost.parse("{2}")
        assert isinstance(katana, Equipment) and katana.is_equipment is True


class TestQuickDrawKatanaBehaviour:
    def test_buff_only_on_controllers_turn(self):
        """On player 0's turn the equipped Prideful Parent (2/2, vigilance)
        attacks for 4; on player 1's turn it is a 2/2 without first strike, so
        blocking Savannah Lions (2/1) it trades with it."""
        parent, lions = card(PridefulParent), card(SavannahLions)
        game = create_game(
            Side(battlefield=[parent, QuickDrawKatana], library=[Forest], mana={ManaType.GREEN: 2}),
            Side(battlefield=[lions], library=[Forest]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, QuickDrawKatanaAbility2, choices=[parent], then=[on_stack(QuickDrawKatanaAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(QuickDrawKatanaAbility2)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, parent)
        t.pass_(0)
        t.pass_(1)
        t.pass_(1, then=[first_strike_damage()])
        t.pass_(0)
        t.pass_(1, then=[life(1, 16)], note="+2/+0 and first strike on player 0's turn")
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, lions, then=[taps(lions)])
        t.pass_(1)
        t.pass_(0)
        t.act(0, parent, scoped={parent: lions})
        t.pass_(1)
        t.pass_(0, then=[moves(lions, Zone.GRAVEYARD), moves(parent, Zone.GRAVEYARD)],
                note="no first strike or +2/+0 on player 1's turn")
        t.run()
