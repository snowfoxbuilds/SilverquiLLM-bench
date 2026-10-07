"""Reference test for FDN 250 — Burnished Hart.

"Search your library for UP TO TWO basic land cards" is a declinable resolution
choice (`choose_object(min=0, max=2)`), not an automatic grab. Basic lands are
detected by the Basic supertype (there is no `is_basic_land` flag).
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_250.card_impl import BurnishedHart, BurnishedHartAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game, shuffled

from silverquillm.table import Table, moves, off_stack, on_stack, taps


class TestBurnishedHartProperties:
    def test_static_data(self):
        h = BurnishedHart(owner=None)
        assert printed_class(h) is BurnishedHart
        assert h.mana_cost == ManaCost.parse("{3}")


def _activate(t: Table, hart) -> None:
    t.act(0, hart, then=[moves(hart, Zone.GRAVEYARD), on_stack(BurnishedHartAbility1, 0)])


class TestBurnishedHartSearch:
    def test_fetches_two_chosen_basics_tapped(self):
        hart, a, b, plains = card(BurnishedHart), card(Forest), card(Forest), card(Plains)
        game = create_game(
            Side(battlefield=[hart], library=[a, plains, b], mana={ManaType.COLORLESS: 3}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _activate(t, hart)
        t.pass_(0, choices=[a, b])
        t.pass_(
            1,
            then=[
                off_stack(BurnishedHartAbility1),
                moves(a, Zone.BATTLEFIELD), taps(a),
                moves(b, Zone.BATTLEFIELD), taps(b),
            ],
            note="both chosen Forests enter tapped; the Plains stays",
        )
        t.run(chance=[shuffled(plains)])

    def test_declinable_search_no_basics(self):
        """With no basic land in the library the ability still resolves (the
        up-to-two search finds nothing), and the Hart is sacrificed."""
        hart, lions = card(BurnishedHart), card(SavannahLions)
        game = create_game(
            Side(battlefield=[hart], library=[lions], mana={ManaType.COLORLESS: 3}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _activate(t, hart)
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurnishedHartAbility1)])
        t.run(chance=[shuffled(lions)])
