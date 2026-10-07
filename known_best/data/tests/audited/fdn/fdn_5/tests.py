"""Celestial Armor uses paid equip or its actual cast/entry attachment.

Equipped, the creature hits for 2 more and flies; the entry attachment also
gives indestructible until end of turn, which shows in what damage kills.
Known-Best enforces no hexproof (#169), so hexproof is not judged here.
"""

from cards.fdn.fdn_5.card_impl import CelestialArmor, CelestialArmorAbility2, CelestialArmorAbility4
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import Equipment, printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


def test_static_data():
    card_ = CelestialArmor()
    assert printed_class(card_) is CelestialArmor and card_.mana_cost == ManaCost.parse("{2}{W}")
    assert card_.equip_cost == ManaCost.parse("{3}{W}") and card_.keywords & Keyword.FLASH
    assert isinstance(card_, Equipment) and card_.is_equipment


def _flying_attack(t, lions, turtle, damage):
    """The Lions attacks; the Turtle cannot block a flier, so it is not blocked."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.act_illegal(
        1, turtle, scoped={turtle: lions}, note="a non-flier cannot block the equipped Lions"
    )
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[damage])


def test_static_buff_after_paid_equip():
    lions, armor, turtle = card(SavannahLions), card(CelestialArmor), card(AegisTurtle)
    game = create_game(
        Side(battlefield=[lions, armor], mana={ManaType.WHITE: 4}),
        Side(battlefield=[turtle]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, CelestialArmorAbility4, choices=[lions], then=[on_stack(CelestialArmorAbility4, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CelestialArmorAbility4)])
    _flying_attack(t, lions, turtle, life(1, 16))
    t.run()


def test_etb_attach_grants_indestructible_until_end_of_turn():
    """Cast in player 0's main phase, the Armor's enters trigger attaches it
    to Savannah Lions, which this turn survives the 1 damage a blocking
    Spectral Sailor deals it; on player 1's turn, with indestructible gone,
    Burst Lightning kills it."""
    lions, armor = card(SavannahLions), card(CelestialArmor)
    sailor, bolt, mountain = card(SpectralSailor), card(BurstLightning), card(Mountain)
    game = create_game(
        Side(hand=[armor], battlefield=[lions], mana={ManaType.WHITE: 3}),
        Side(hand=[bolt], battlefield=[sailor, mountain], library=[Mountain]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, armor, then=[moves(armor, Zone.STACK)])
    t.pass_(0, choices=[lions])
    t.pass_(1, then=[moves(armor, Zone.BATTLEFIELD), on_stack(CelestialArmorAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CelestialArmorAbility2)])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, sailor, scoped={sailor: lions})
    t.pass_(0)
    t.pass_(1, then=[moves(sailor, Zone.GRAVEYARD)], note="the indestructible Lions survives 1 damage")
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    t.act(1, mountain, then=[taps(mountain)])
    t.act(1, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.run()
