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
from cards.fdn.fdn_159.card_impl import MockingSprite
from cards.fdn.fdn_172.card_impl import EatenAlive, EatenAliveAbility1
from cards.fdn.fdn_210.card_impl import ThrillOfPossibility
from cards.fdn.fdn_272.card_impl import Plains
from engine.casting import CastingError, cast_spell, cast_spell_free
from engine.decisions import Decision
from engine.queries import Answer
from engine.types import ManaType, Phase, Zone
from test_interface import Side, card, create_game

from table import Table, moves

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


def _sprite_game(monkeypatch, mana, *, pay_with_mana=True):
    """Player 0 controls Mocking Sprite (instants and sorceries cost {1} less)
    and holds Eaten Alive, aimed at player 1's Lions. Questions are answered
    directly, since no script plays outside ``run``: the additional cost is
    paid with mana or by sacrifice, and the only creature to sacrifice is the
    Sprite. Returns the questions asked."""
    import engine.casting

    game = create_game(
        Side(hand=[EatenAlive], battlefield=[MockingSprite], library=[Plains], mana=mana),
        Side(battlefield=[SavannahLions], library=[Plains]),
        start=MAIN,
    )
    player = game.players[0]
    spell = game.get_hand(player).get_all()[0]
    sprite = game.get_battlefield(player).get_all()[0]
    lions = game.get_battlefield(game.players[1]).get_all()[0]
    monkeypatch.setattr(engine.casting, "_query_target", lambda *args, **kwargs: lions)
    asked = []

    def answer(query):
        asked.append(query)
        if query.prompt == _HOW_TO_PAY:
            wanted = 1 if pay_with_mana else 0
            option = next(o for o in query.options if dict(o.attrs).get("index") == wanted)
            return Answer(selected=(option,))
        return Answer(selected=(query.options[0],))

    monkeypatch.setattr(player, "answer", answer, raising=False)
    return game, player, spell, sprite, asked


_HOW_TO_PAY = "Choose how to pay the additional cost"


def _asked_how_to_pay(asked):
    return [q for q in asked if q.prompt == _HOW_TO_PAY]


def test_a_free_cast_pays_the_reduced_additional_mana(monkeypatch):
    """{3}{B} less {1}: a free cast with the Sprite out spends {2}{B} of {3}{B}
    and keeps the Sprite."""
    game, player, spell, sprite, asked = _sprite_game(
        monkeypatch, {ManaType.BLACK: 1, ManaType.COLORLESS: 3})
    cast_spell_free(game, player, spell, Zone.HAND)
    assert player.mana_pool.total() == 1
    assert _asked_how_to_pay(asked)
    assert game.get_battlefield(player).contains(sprite)


def test_a_free_cast_with_too_little_mana_sacrifices_instead(monkeypatch):
    """With {1}{B}, less than the reduced {2}{B}, only the sacrifice is
    offered; the Sprite is sacrificed and no mana is spent."""
    game, player, spell, sprite, asked = _sprite_game(
        monkeypatch, {ManaType.BLACK: 1, ManaType.COLORLESS: 1})
    cast_spell_free(game, player, spell, Zone.HAND)
    assert not _asked_how_to_pay(asked)
    assert player.mana_pool.total() == 2
    assert game.get_graveyard(player).contains(sprite)


def test_a_free_cast_may_choose_the_sacrifice_when_both_are_payable(monkeypatch):
    game, player, spell, sprite, asked = _sprite_game(
        monkeypatch, {ManaType.BLACK: 1, ManaType.COLORLESS: 3}, pay_with_mana=False)
    cast_spell_free(game, player, spell, Zone.HAND)
    assert _asked_how_to_pay(asked)
    assert player.mana_pool.total() == 4
    assert game.get_graveyard(player).contains(sprite)


def test_a_normal_cast_pays_the_reduced_total(monkeypatch):
    """{B} plus {3}{B}, less {1}: {2}{B}{B} out of {3}{B}{B}, keeping the
    Sprite."""
    game, player, spell, sprite, _ = _sprite_game(
        monkeypatch, {ManaType.BLACK: 2, ManaType.COLORLESS: 3})
    cast_spell(game, player, spell)
    assert player.mana_pool.total() == 1
    assert game.get_battlefield(player).contains(sprite)


def test_a_normal_cast_short_of_the_reduced_total_sacrifices_instead(monkeypatch):
    game, player, spell, sprite, asked = _sprite_game(
        monkeypatch, {ManaType.BLACK: 2, ManaType.COLORLESS: 1})
    cast_spell(game, player, spell)
    assert not _asked_how_to_pay(asked)
    assert player.mana_pool.total() == 2
    assert game.get_graveyard(player).contains(sprite)


def test_a_free_cast_with_exactly_the_reduced_mana_may_pay_it(monkeypatch):
    """{2}{B}, exactly the reduced {3}{B}: the mana alternative is offered and
    paid in full, keeping the Sprite."""
    game, player, spell, sprite, asked = _sprite_game(
        monkeypatch, {ManaType.BLACK: 1, ManaType.COLORLESS: 2})
    cast_spell_free(game, player, spell, Zone.HAND)
    assert _asked_how_to_pay(asked)
    assert player.mana_pool.total() == 0
    assert game.get_battlefield(player).contains(sprite)
