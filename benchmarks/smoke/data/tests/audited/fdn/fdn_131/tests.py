"""Audited tests for FDN 131 — Ravenous Amulet.

"{1}, {T}, Sacrifice a creature: Draw a card and put a soul counter on this
artifact. Activate only as a sorcery." The soul counters only show through
the Amulet's drain, whose Known-Best form pays its sacrifice as it resolves
(#169), so the drain is guarded by the Known-Best platform checks instead.
"""

from __future__ import annotations

from cards.fdn.fdn_131.card_impl import RavenousAmulet, RavenousAmuletAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves, off_stack, on_stack, taps


def test_sacrificing_a_creature_draws_a_card():
    amulet, lions, drawn = card(RavenousAmulet), card(SavannahLions), card(Forest)
    game = create_game(
        Side(battlefield=[amulet, lions], library=[drawn], mana={ManaType.COLORLESS: 1}),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(
        0,
        RavenousAmuletAbility1,
        then=[taps(amulet), moves(lions, Zone.GRAVEYARD), on_stack(RavenousAmuletAbility1, 0)],
        note="the Lions is sacrificed as part of the cost",
    )
    t.pass_(0)
    t.pass_(1, then=[off_stack(RavenousAmuletAbility1), moves(drawn, Zone.HAND)])
    t.run()
