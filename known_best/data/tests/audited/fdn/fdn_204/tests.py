"""Audited test for FDN 204 — Krenko, Mob Boss.

"{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins
you control." With only Krenko, itself a Goblin, X is 1; the next turn Krenko
and that token are two Goblins, so the token counts as a Goblin.
"""

from __future__ import annotations

from cards.fdn.fdn_204.card_impl import KrenkoMobBoss, KrenkoMobBossAbility1
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Phase, Side, card, create_game

from silverquillm.table import Table, appears, off_stack, on_stack, taps


def _mint(t, krenko, tokens):
    t.act(0, krenko, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(KrenkoMobBossAbility1), *(appears(0) for _ in range(tokens))])


class TestKrenkoMobBossMint:
    def test_activated_ability_mints_11_red_goblin_tokens(self) -> None:
        krenko = card(KrenkoMobBoss)
        game = create_game(
            Side(battlefield=[krenko], library=[Plains]),
            Side(library=[Plains]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _mint(t, krenko, 1)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _mint(t, krenko, 2)
        t.run()
