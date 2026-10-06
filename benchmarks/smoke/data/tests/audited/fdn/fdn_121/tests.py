"""Reference test for FDN 121 — Koma, World-Eater (its Serpent tokens).

"Whenever Koma deals combat damage to a player, create four 3/3 blue Serpent
creature tokens named Koma's Coil." Koma attacks unblocked for 8, four tokens
appear, and one of them shows it is a 3/3 by attacking on the next turn.
"""

from __future__ import annotations

from cards.fdn.fdn_121.card_impl import KomaWorldEater, KomaWorldEaterAbility4
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Side, Step, card, create_game, token

from silverquillm.table import Table, appears, life, off_stack, on_stack, taps


def _unblocked(t, *attackers, then):
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, *attackers, then=[taps(a) for a in attackers])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=then)


class TestKomaToken:
    def test_combat_damage_mints_four_serpents(self) -> None:
        koma = card(KomaWorldEater)
        game = create_game(
            Side(battlefield=[koma], library=[Forest]),
            Side(library=[Forest]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        _unblocked(t, koma, then=[life(1, 12), on_stack(KomaWorldEaterAbility4, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(KomaWorldEaterAbility4), appears(0), appears(0), appears(0), appears(0)])
        t.pass_to(Step.UPKEEP, 1)
        _unblocked(t, token(1), then=[life(1, 9)])
        t.run()
