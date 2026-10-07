"""Goldvein Pick grants its equip bonus and creates Treasure through combat."""

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_253.card_impl import GoldveinPick, GoldveinPickAbility2, GoldveinPickAbility3
from engine.card import Equipment, printed_class
from engine.types import ManaCost
from test_interface import (
    Decision,
    ManaType,
    Phase,
    Side,
    Step,
    Zone,
    card,
    create_game,
    player,
    token,
)

from silverquillm.table import Table, appears, ceases, life, moves, off_stack, on_stack, taps


def arrange(*, hand=()):
    """Player 0 equips Goldvein Pick to Savannah Lions, then attacks with it
    unblocked; its combat damage triggers the Pick."""
    lions, pick = card(SavannahLions), card(GoldveinPick)
    game = create_game(
        Side(hand=list(hand), battlefield=[lions, pick], mana={ManaType.COLORLESS: 1}),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, GoldveinPickAbility3, choices=[lions], then=[on_stack(GoldveinPickAbility3, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(GoldveinPickAbility3)])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 17), on_stack(GoldveinPickAbility2, 0)], note="the equipped Lions deals 3")
    t.pass_(0)
    t.pass_(1, then=[off_stack(GoldveinPickAbility2), appears(0)])
    return t


def test_static_data():
    card = GoldveinPick()
    assert printed_class(card) is GoldveinPick and card.mana_cost == ManaCost.parse("{2}")
    assert isinstance(card, Equipment) and card.equip_cost == ManaCost.parse("{1}")


def test_grants_plus_one_plus_one():
    arrange().run()


def test_combat_damage_to_player_makes_treasure():
    bolt = card(BurstLightning)
    t = arrange(hand=[bolt])
    treasure = token(1)
    t.act(0, treasure, choices=[Decision.color("R")], then=[ceases(treasure)], note="the Treasure makes red mana")
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 15)])
    t.run()
