"""Known-Best additional costs (rules 118.8, 601.2b, 601.2f–h): the caster
announces which alternative they pay, its mana joins the total cost, its
sacrifice or discard is paid with it, and a spell cast without paying its
mana cost still owes them (rule 118.9d).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_55.card_impl import ArbiterOfWoe
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_172.card_impl import EatenAlive, EatenAliveAbility1
from cards.fdn.fdn_210.card_impl import ThrillOfPossibility
from cards.fdn.fdn_272.card_impl import Plains
from engine.casting import CastingError, cast_spell_free
from engine.decisions import Decision
from engine.types import ManaType, Phase, Zone
from test_interface import Side, card, create_game

from silverquillm.table import Table, moves

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def test_both_alternatives_payable_lets_the_caster_choose_mana():
    """With a creature and {3}{B}{B}, the caster is asked which alternative to
    pay; choosing the mana keeps the creature."""
    eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 3}),
        Side(battlefield=[theirs], library=[card(Plains)]),
        start=MAIN,
    ))
    t.act(0, eaten, Decision.ability(index=1, printed=EatenAliveAbility1), choices=[theirs],
          then=[moves(eaten, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(theirs, Zone.EXILE)])
    t.run()


def test_thrill_of_possibility_discards_a_card_as_it_is_cast():
    thrill, other = card(ThrillOfPossibility), card(Plains)
    draws = [card(Plains), card(Plains)]
    t = Table(create_game(
        Side(hand=[thrill, other], library=draws, mana={ManaType.RED: 2}),
        Side(library=[card(Plains)]),
        start=MAIN,
    ))
    t.act(0, thrill, then=[moves(thrill, Zone.STACK), moves(other, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[moves(thrill, Zone.GRAVEYARD), *(moves(d, Zone.HAND) for d in draws)])
    t.run()


def test_thrill_of_possibility_with_nothing_to_discard_cannot_be_cast():
    thrill = card(ThrillOfPossibility)
    t = Table(create_game(
        Side(hand=[thrill], library=[card(Plains)], mana={ManaType.RED: 2}),
        Side(library=[card(Plains)]),
        start=MAIN,
    ))
    t.act_illegal(0, thrill)
    t.run()


def test_arbiter_of_woe_needs_a_creature_to_sacrifice():
    arbiter = card(ArbiterOfWoe)
    t = Table(create_game(
        Side(hand=[arbiter], library=[card(Plains)], mana={ManaType.BLACK: 6}),
        Side(library=[card(Plains)]),
        start=MAIN,
    ))
    t.act_illegal(0, arbiter)
    t.run()


def _free_cast_game(monkeypatch, *, mana=None):
    """Eaten Alive in player 0's hand, cast directly; its target question is
    answered with player 1's Lions, since no script plays outside ``run``."""
    import engine.casting

    game = create_game(
        Side(hand=[EatenAlive], library=[Plains], mana=mana or {}),
        Side(battlefield=[SavannahLions], library=[Plains]),
        start=MAIN,
    )
    player = game.players[0]
    spell = game.get_hand(player).get_all()[0]
    lions = game.get_battlefield(game.players[1]).get_all()[0]
    monkeypatch.setattr(engine.casting, "_query_target", lambda *args, **kwargs: lions)
    return game, player, spell


def test_a_free_cast_still_owes_the_additional_cost(monkeypatch):
    game, player, spell = _free_cast_game(monkeypatch)
    with pytest.raises(CastingError):
        cast_spell_free(game, player, spell, Zone.HAND)
    assert game.get_hand(player).contains(spell)


def test_a_free_cast_pays_the_additional_mana(monkeypatch):
    game, player, spell = _free_cast_game(monkeypatch, mana={ManaType.BLACK: 1, ManaType.COLORLESS: 3})
    cast_spell_free(game, player, spell, Zone.HAND)
    assert player.mana_pool.total() == 0
