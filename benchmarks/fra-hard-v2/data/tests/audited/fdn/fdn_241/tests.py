"""Reference test for FDN 241 — Heroic Reinforcements.

Heroic Reinforcements creates two 1/1 white Soldier creature tokens, and until
end of turn creatures its caster controls get +1/+1 and gain haste. The tokens
show what they are in play: this turn they attack at once as 2/2s, and on the
next turn, the pump gone, as 1/1s.
"""

from __future__ import annotations

from cards.fdn.fdn_241.card_impl import HeroicReinforcements
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, taps


def _attack_with_both(t: Table, *, then) -> None:
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    soldiers = token(1), token(2)
    t.act(0, *soldiers, then=[taps(s) for s in soldiers])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=then)


class TestHeroicReinforcementsMint:
    def test_mints_two_11_white_soldier_tokens(self) -> None:
        spell = card(HeroicReinforcements)
        game = create_game(
            Side(
                hand=[spell],
                library=[card(Plains)],
                mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2},
            ),
            Side(library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, spell, then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), appears(0), appears(0)])
        _attack_with_both(t, then=[life(1, 16)])
        _attack_with_both(t, then=[life(1, 14)])
        t.run()
