"""Fake Your Own Death resolves, returns a dying creature and expires at cleanup.

"Until end of turn, target creature gets +2/+0 and gains 'When this creature
dies, return it to the battlefield tapped under its owner's control and you
create a Treasure token.'" Player 0 casts it on Savannah Lions (2/1); its +2
shows in combat, and the Lions is destroyed by Stroke of Midnight or
sacrificed to Hungry Ghoul.
"""

from cards.fdn.fdn_62.card_impl import HungryGhoul, HungryGhoulAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_148.card_impl import StrokeOfMidnight
from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath, FakeYourOwnDeathAbility1
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import Instant
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps


def arrange(*, extra_mana=0, hand=(), battlefield=()):
    """Player 0's main phase: Fake Your Own Death is cast on Savannah Lions,
    and is left on the stack."""
    spell, lions, ghoul = card(FakeYourOwnDeath), card(SavannahLions), card(HungryGhoul)
    game = create_game(
        Side(
            hand=[spell, *hand],
            battlefield=[lions, ghoul, *battlefield],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1 + extra_mana},
        ),
        Side(library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, spell, choices=[lions], then=[moves(spell, Zone.STACK)])
    return t, spell, lions, ghoul


def _resolve(t, spell):
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD)])


def test_is_instant():
    assert isinstance(FakeYourOwnDeath(), Instant)


def test_mana_cost():
    assert FakeYourOwnDeath().mana_cost == ManaCost.parse("{1}{B}")


def test_resolution_applies_buff_and_leaves_stack():
    """The 2/1 Lions attacks as a 4/1."""
    t, spell, lions, _ghoul = arrange()
    _resolve(t, spell)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 16)])
    t.run()


def test_death_returns_tapped_and_creates_treasure():
    """Stroke of Midnight destroys the Lions (and makes its controller a
    Human token); the Lions returns tapped, and a Treasure is made."""
    stroke = card(StrokeOfMidnight)
    plains = [card(Plains) for _ in range(3)]
    t, spell, lions, _ghoul = arrange(hand=[stroke], battlefield=plains)
    _resolve(t, spell)
    for land in plains:
        t.act(0, land, then=[taps(land)])
    t.act(0, stroke, choices=[lions], then=[moves(stroke, Zone.STACK)])
    t.pass_(0)
    t.pass_(
        1,
        then=[moves(stroke, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD), appears(0), on_stack(FakeYourOwnDeathAbility1, 0)],
    )
    t.pass_(0)
    t.pass_(
        1,
        then=[off_stack(FakeYourOwnDeathAbility1), moves(lions, Zone.BATTLEFIELD), taps(lions), appears(0)],
        note="the Lions returns tapped, and a Treasure is made",
    )
    t.run()


def test_departed_target_fizzles_without_buff_or_treasure():
    """The Lions is sacrificed in response, so Fake Your Own Death does
    nothing: the Lions stays in the graveyard and no Treasure is made."""
    t, spell, lions, _ghoul = arrange(extra_mana=1)
    t.act(0, HungryGhoulAbility1, choices=[lions], then=[moves(lions, Zone.GRAVEYARD), on_stack(HungryGhoulAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(HungryGhoulAbility1)])
    _resolve(t, spell)
    t.run()
