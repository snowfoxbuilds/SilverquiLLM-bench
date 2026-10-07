"""Audited tests for FDN 687 — Demolition Field.

"{T}: Add {C}. {2}, {T}, Sacrifice this land: Destroy target nonbasic land an
opponent controls. That land's controller may search their library for a
basic land card, put it onto the battlefield, then shuffle. You may search
your library for a basic land card, put it onto the battlefield, then
shuffle." The target is chosen as the ability is activated; both searches
happen as it resolves, the destroyed land's controller first. Each player
chooses whether to search; one who searches may find nothing (CR 701.23b)
and shuffles either way.
"""

from __future__ import annotations

from cards.fdn.fdn_139.card_impl import CatharCommando
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_264.card_impl import RoguesPassage
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.fdn_669.card_impl import BasiliskCollar
from cards.fdn.fdn_687.card_impl import (
    DemolitionField,
    DemolitionFieldAbility1,
    DemolitionFieldAbility2,
)
from test_interface import Decision, Phase, Side, Zone, ability, card, create_game, shuffled

from table import Table, moves, off_stack, on_stack, shuffles, taps

YES, NO = Decision.yes(), Decision.no()


def _field(theirs, *, my_library=(), their_library=(), fields=1, plains=2):
    """Player 0's main phase: Demolition Fields and Plains to pay {2} for each."""
    mine = [card(DemolitionField) for _ in range(fields)]
    lands = [card(Plains) for _ in range(plains)]
    game = create_game(
        Side(battlefield=[*mine, *lands], library=list(my_library)),
        Side(battlefield=list(theirs), library=list(their_library)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    for land in lands[:2]:
        t.act(0, land, then=[taps(land)])
    return t, mine, lands


def _activate(t, field, target):
    t.act(0, ability(field, DemolitionFieldAbility2), choices=[target],
          then=[moves(field, Zone.GRAVEYARD), on_stack(DemolitionFieldAbility2, 0)])


class TestDemolitionFieldAbility:
    def test_destroys_the_land_and_both_players_search(self):
        """Rogue's Passage is destroyed; player 1 finds a Forest, then player 0
        a Plains, each onto the battlefield untapped, and both shuffle."""
        passage = card(RoguesPassage)
        their_forest, their_other = card(Forest), card(Mountain)
        my_plains, my_other = card(Plains), card(Mountain)
        t, (field,), _ = _field([passage], my_library=[my_plains, my_other],
                                their_library=[their_forest, their_other])
        _activate(t, field, passage)
        t.pass_(0, choices=[YES, my_plains])
        t.pass_(1, choices=[YES, their_forest], then=[
            off_stack(DemolitionFieldAbility2),
            moves(passage, Zone.GRAVEYARD),
            moves(their_forest, Zone.BATTLEFIELD),
            moves(my_plains, Zone.BATTLEFIELD),
        ])
        t.run(chance=[shuffled(their_other), shuffled(my_other)])

    def test_a_search_with_no_basic_land_still_shuffles(self):
        """Player 1's library holds no basic land; they search anyway, find
        nothing and shuffle it into a new order. Player 0 declines."""
        passage = card(RoguesPassage)
        lions, commando = card(SavannahLions), card(CatharCommando)
        t, (field,), _ = _field([passage], their_library=[lions, commando])
        _activate(t, field, passage)
        t.pass_(0, choices=[NO])
        t.pass_(1, choices=[YES], then=[
            off_stack(DemolitionFieldAbility2),
            moves(passage, Zone.GRAVEYARD),
            shuffles(1, commando, lions),
        ])
        t.run(chance=[shuffled(commando, lions)])

    def test_a_player_may_find_nothing_though_a_basic_land_is_there(self):
        """Player 1 searches and chooses no card although a Forest is there:
        the Forest stays in the library, which is shuffled."""
        passage = card(RoguesPassage)
        forest, lions = card(Forest), card(SavannahLions)
        t, (field,), _ = _field([passage], their_library=[forest, lions])
        _activate(t, field, passage)
        t.pass_(0, choices=[NO])
        t.pass_(1, choices=[YES], then=[
            off_stack(DemolitionFieldAbility2),
            moves(passage, Zone.GRAVEYARD),
            shuffles(1, lions, forest),
        ])
        t.run(chance=[shuffled(lions, forest)])

    def test_declining_to_search_leaves_the_library_as_it_was(self):
        """Both players decline: nothing is searched and nothing is shuffled,
        so both libraries keep their order."""
        passage = card(RoguesPassage)
        t, (field,), _ = _field([passage], my_library=[card(Forest), card(Mountain)],
                                their_library=[card(Forest), card(SavannahLions)])
        _activate(t, field, passage)
        t.pass_(0, choices=[NO])
        t.pass_(1, choices=[NO], then=[off_stack(DemolitionFieldAbility2), moves(passage, Zone.GRAVEYARD)])
        t.run()

    def test_an_illegal_target_on_resolution_means_no_search(self):
        """Player 0 activates both Fields at the same Rogue's Passage; the
        second resolves first and destroys it, both players declining to
        search. The first then has no legal target: nobody is asked to
        search and nothing is shuffled, while its costs stay paid."""
        passage = card(RoguesPassage)
        t, (first, second), lands = _field([passage], their_library=[card(Forest), card(SavannahLions)],
                                            fields=2, plains=4)
        _activate(t, first, passage)
        for land in lands[2:]:
            t.act(0, land, then=[taps(land)])
        _activate(t, second, passage)
        t.pass_(0, choices=[NO])
        t.pass_(1, choices=[NO], then=[off_stack(DemolitionFieldAbility2), moves(passage, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DemolitionFieldAbility2)])
        t.run()

    def test_only_an_opponents_nonbasic_land_can_be_targeted(self):
        """With only a basic Mountain on player 1's side the ability has no
        legal target: it is not offered, or offered and rejected, and the
        Field stays."""
        mountain = card(Mountain)
        t, (field,), _ = _field([mountain])
        t.act_illegal(0, ability(field, DemolitionFieldAbility2), choices=[mountain])
        t.run()


class TestDemolitionFieldCosts:
    def test_the_ability_needs_two_mana(self):
        """With one Plains tapped for {W} the Field's {2} cannot be paid."""
        passage = card(RoguesPassage)
        field, plains = card(DemolitionField), card(Plains)
        t = Table(create_game(Side(battlefield=[field, plains]), Side(battlefield=[passage]),
                              start=(Phase.PRECOMBAT_MAIN, 0)))
        t.act(0, plains, then=[taps(plains)])
        t.act_illegal(0, ability(field, DemolitionFieldAbility2), choices=[passage])
        t.run()

    def test_it_taps_for_colorless_mana(self):
        """The Field's {C} pays for Basilisk Collar's {1}."""
        field, collar = card(DemolitionField), card(BasiliskCollar)
        t = Table(create_game(Side(battlefield=[field], hand=[collar]), Side(),
                              start=(Phase.PRECOMBAT_MAIN, 0)))
        t.act(0, ability(field, DemolitionFieldAbility1), then=[taps(field)])
        t.act(0, collar, then=[moves(collar, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(collar, Zone.BATTLEFIELD)])
        t.run()
