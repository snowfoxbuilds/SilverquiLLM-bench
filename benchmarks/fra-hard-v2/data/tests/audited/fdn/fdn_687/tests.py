"""Audited tests for FDN 687 — Demolition Field.

"{T}: Add {C}. {2}, {T}, Sacrifice this land: Destroy target nonbasic land an
opponent controls. That land's controller may search their library for a
basic land card, put it onto the battlefield, then shuffle. You may search
your library for a basic land card, put it onto the battlefield, then
shuffle." The target is chosen as the ability is activated; both searches
happen as it resolves, the destroyed land's controller first.
"""

from __future__ import annotations

from cards.fdn.fdn_264.card_impl import RoguesPassage
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.fdn_687.card_impl import DemolitionField, DemolitionFieldAbility2
from engine.card import Land, printed_class
from test_interface import Phase, Side, Zone, card, create_game, shuffled

from silverquillm.table import Table, moves, off_stack, on_stack, taps


class TestDemolitionFieldProperties:
    def test_static_data(self):
        field = DemolitionField(owner=None)
        assert printed_class(field) is DemolitionField
        assert isinstance(field, Land)


def _field(theirs, *, my_library=(), their_library=()):
    """Player 0's main phase: Demolition Field and two Plains to pay {2}."""
    field = card(DemolitionField)
    plains = [card(Plains), card(Plains)]
    game = create_game(
        Side(battlefield=[field, *plains], library=list(my_library)),
        Side(battlefield=list(theirs), library=list(their_library)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    for land in plains:
        t.act(0, land, then=[taps(land)])
    return t, field


class TestDemolitionFieldAbility:
    def test_destroys_the_land_and_both_players_search(self):
        """Rogue's Passage is destroyed; player 1 finds a Forest, then player 0
        a Plains, each onto the battlefield untapped."""
        passage = card(RoguesPassage)
        their_forest, their_other = card(Forest), card(Mountain)
        my_plains, my_other = card(Plains), card(Mountain)
        t, field = _field([passage], my_library=[my_plains, my_other],
                          their_library=[their_forest, their_other])
        t.act(0, DemolitionFieldAbility2, choices=[passage],
              then=[moves(field, Zone.GRAVEYARD), on_stack(DemolitionFieldAbility2, 0)])
        t.pass_(0, choices=[my_plains])
        t.pass_(1, choices=[their_forest], then=[
            off_stack(DemolitionFieldAbility2),
            moves(passage, Zone.GRAVEYARD),
            moves(their_forest, Zone.BATTLEFIELD),
            moves(my_plains, Zone.BATTLEFIELD),
        ])
        t.run(chance=[shuffled(their_other), shuffled(my_other)])

    def test_only_an_opponents_nonbasic_land_can_be_targeted(self):
        """With only a basic Mountain on player 1's side the ability has no
        legal target: it is not offered, or offered and rejected, and the
        Field stays."""
        mountain = card(Mountain)
        t, _ = _field([mountain])
        t.act_illegal(0, DemolitionFieldAbility2, choices=[mountain])
        t.run()
