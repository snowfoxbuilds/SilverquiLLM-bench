"""Inside Information, played at the table.

Player 0 casts Inside Information at player 1. The exiled cards are player 1's;
player 0 may play them this turn, paying life equal to a spell's mana value
instead of its mana cost — which shows in player 0's life total and in what an
empty mana pool can still cast.
"""

from card_impl import InsideInformation
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_173.card_impl import Exsanguinate
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fut.fut_78.card_impl import SlaughterPact, SlaughterPactAbility2
from test_interface import Decision, ManaType, Phase, Side, Step, Zone, card, create_game, player

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps, wins

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _plains(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(library, *, x: int = 0, hand=(), extra_mana=None, life_total: int = 20, seat1_hand=(),
          seat1_battlefield=(), seat1_mana=None):
    info = card(InsideInformation)
    mana = {ManaType.BLACK: 2, ManaType.COLORLESS: x}
    for kind, amount in (extra_mana or {}).items():
        mana[kind] = mana.get(kind, 0) + amount
    game = create_game(
        Side(hand=[info, *hand], library=_plains(), mana=mana, life=life_total),
        Side(library=list(library), hand=list(seat1_hand), battlefield=list(seat1_battlefield),
             mana=dict(seat1_mana or {})),
        start=MAIN,
    )
    return game, info


def _cast_info(t: Table, info, library, x: int) -> None:
    """Player 0 casts Inside Information with X = ``x`` at player 1; the top
    ``x`` cards of player 1's library are exiled."""
    t.act(0, info, choices=[Decision.number(x), player(1)], then=[moves(info, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(info, Zone.GRAVEYARD), *(moves(c, Zone.EXILE) for c in library[:x])])


def _resolve(t: Table, *, then=(), note: str = "") -> None:
    t.pass_(0)
    t.pass_(1, then=list(then), note=note)


def test_x_cards_are_exiled_from_the_top_of_the_opponents_library():
    library = [card(SavannahLions), card(BurstLightning), card(Plains), card(Plains)]
    game, info = _game(library, x=2)
    t = Table(game)
    _cast_info(t, info, library, 2)
    t.run()


def test_x_zero_exiles_nothing():
    library = _plains(3)
    game, info = _game(library)
    t = Table(game)
    _cast_info(t, info, library, 0)
    t.run()


def test_x_greater_than_the_library_exiles_what_there_is():
    """Player 1's whole library is exiled; they lose only when they next draw."""
    library = [card(SavannahLions), card(Plains)]
    game, info = _game(library, x=3)
    t = Table(game)
    t.act(0, info, choices=[Decision.number(3), player(1)], then=[moves(info, Zone.STACK)])
    _resolve(t, then=[moves(info, Zone.GRAVEYARD), *(moves(c, Zone.EXILE) for c in library)])
    t.pass_to(Step.UPKEEP, 1)
    t.pass_(1)
    t.pass_(0)
    t.run()


def test_an_exiled_instant_is_cast_for_life_equal_to_its_mana_value():
    bolt = card(BurstLightning)
    library = [bolt, card(Plains)]
    game, info = _game(library, x=1)
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK, seat=0), life(0, 19)],
          note="no mana is left: the spell is paid with 1 life")
    _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)], note="it goes to its owner's graveyard")
    t.run()


def test_an_exiled_creature_enters_under_the_casters_control():
    lions = card(SavannahLions)
    library = [lions, card(Plains)]
    game, info = _game(library, x=1)
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, lions, then=[moves(lions, Zone.STACK, seat=0), life(0, 19)])
    _resolve(t, then=[moves(lions, Zone.BATTLEFIELD, seat=0)])
    t.run()


def test_life_is_paid_even_with_mana_in_the_pool():
    """With {R} still floating, the exiled Lions costs 1 life; the {R} then
    pays for Burst Lightning from hand."""
    lions, own_bolt = card(SavannahLions), card(BurstLightning)
    library = [lions, card(Plains)]
    game, info = _game(library, x=1, hand=[own_bolt], extra_mana={ManaType.RED: 1})
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, lions, then=[moves(lions, Zone.STACK, seat=0), life(0, 19)])
    _resolve(t, then=[moves(lions, Zone.BATTLEFIELD, seat=0)])
    t.act(0, own_bolt, choices=[player(1)], then=[moves(own_bolt, Zone.STACK)])
    _resolve(t, then=[moves(own_bolt, Zone.GRAVEYARD), life(1, 18)])
    t.run()


def test_several_exiled_spells_may_be_cast():
    bolt, wave = card(BurstLightning), card(Boltwave)
    library = [bolt, wave, card(Plains)]
    game, info = _game(library, x=2)
    t = Table(game)
    _cast_info(t, info, library, 2)
    t.act(0, wave, then=[moves(wave, Zone.STACK, seat=0), life(0, 19)])
    _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK, seat=0), life(0, 18)])
    _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 15)])
    t.run()


def test_a_spell_with_x_cast_for_life_has_x_zero():
    """Exsanguinate (mana value 2) costs 2 life, and with X = 0 drains nobody."""
    drain = card(Exsanguinate)
    library = [drain, card(Plains)]
    game, info = _game(library, x=1, extra_mana={ManaType.BLACK: 3})
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, drain, choices=[Decision.number(0)], then=[moves(drain, Zone.STACK, seat=0), life(0, 18)])
    _resolve(t, then=[moves(drain, Zone.GRAVEYARD)])
    t.run()


def test_an_exiled_land_is_played_without_paying_life_and_uses_the_land_play():
    first, second = card(Plains), card(Island)
    library = [first, second, card(Plains)]
    game, info = _game(library, x=2)
    t = Table(game)
    _cast_info(t, info, library, 2)
    t.act(0, first, then=[moves(first, Zone.BATTLEFIELD, seat=0)])
    t.act_illegal(0, second, note="the turn's land play is used")
    t.run()


def test_the_exiled_cards_keep_normal_timing():
    """Boltwave is a sorcery: it cannot be cast from exile while player 0's
    own Burst Lightning is on the stack."""
    wave, own_bolt = card(Boltwave), card(BurstLightning)
    library = [wave, card(Plains)]
    game, info = _game(library, x=1, hand=[own_bolt], extra_mana={ManaType.RED: 1})
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, own_bolt, choices=[player(1)], then=[moves(own_bolt, Zone.STACK)])
    t.act_illegal(0, wave)
    _resolve(t, then=[moves(own_bolt, Zone.GRAVEYARD), life(1, 18)])
    t.act(0, wave, then=[moves(wave, Zone.STACK, seat=0), life(0, 19)])
    _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 15)])
    t.run()


def test_the_opponent_gains_no_permission():
    """Player 1 cannot cast their own exiled Burst Lightning, even with {R}."""
    bolt = card(BurstLightning)
    library = [bolt, card(Plains)]
    game, info = _game(library, x=1, seat1_mana={ManaType.RED: 1})
    t = Table(game)
    t.act(0, info, choices=[Decision.number(1), player(1)], then=[moves(info, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(info, Zone.GRAVEYARD), moves(bolt, Zone.EXILE)])
    t.pass_(0)
    t.act_illegal(1, bolt, choices=[player(0)])
    t.run()


def test_the_permission_ends_with_the_turn():
    bolt = card(BurstLightning)
    library = [bolt, card(Plains), card(Plains)]
    game, info = _game(library, x=1)
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.pass_to(Step.UPKEEP, 1)
    t.pass_(1)
    t.act_illegal(0, bolt, choices=[player(1)], note="it is player 1's turn now")
    t.run()


def test_a_spell_costing_more_life_than_the_player_has_cannot_be_cast():
    """At 2 life, Hero's Downfall (mana value 3) cannot be paid for."""
    downfall, lions = card(HerosDownfall), card(SavannahLions)
    library = [downfall, card(Plains)]
    game, info = _game(library, x=1, life_total=2, seat1_battlefield=[lions])
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act_illegal(0, downfall, choices=[lions])
    t.run()


def test_paying_exactly_the_remaining_life_loses_the_game():
    downfall, lions = card(HerosDownfall), card(SavannahLions)
    library = [downfall, card(Plains)]
    game, info = _game(library, x=1, life_total=3, seat1_battlefield=[lions])
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, downfall, choices=[lions], then=[moves(downfall, Zone.STACK, seat=0), life(0, 0), wins(1)])
    t.run()


def test_a_countered_exiled_spell_does_not_refund_the_life():
    bolt, offer, island = card(BurstLightning), card(AnOfferYouCantRefuse), card(Island)
    library = [bolt, card(Plains)]
    game, info = _game(library, x=1, seat1_hand=[offer], seat1_battlefield=[island])
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK, seat=0), life(0, 19)])
    t.pass_(0)
    t.act(1, island, then=[taps(island)])
    t.act(1, offer, choices=[bolt], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(bolt, Zone.GRAVEYARD), appears(0), appears(0)])
    t.run()


def test_a_spell_with_mana_value_zero_is_cast_for_no_life():
    """Slaughter Pact's mana value is 0, so at 1 life player 0 still casts it,
    paying nothing, and stays at 1."""
    pact, lions = card(SlaughterPact), card(SavannahLions)
    library = [pact, card(Plains)]
    game, info = _game(library, x=1, life_total=1, seat1_battlefield=[lions])
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, pact, choices=[lions], then=[moves(pact, Zone.STACK, seat=0)], note="0 life is paid")
    _resolve(t, then=[moves(pact, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.run()


def test_a_pact_cast_this_way_still_comes_due_for_its_caster():
    """Paying life replaces only the mana cost: the pact player 0 cast from
    player 1's exile comes due at player 0's next upkeep, and with no mana to
    pay {2}{B} player 0 loses."""
    pact, lions = card(SlaughterPact), card(SavannahLions)
    library = [pact, card(Plains), card(Plains)]
    game, info = _game(library, x=1, seat1_battlefield=[lions])
    t = Table(game)
    _cast_info(t, info, library, 1)
    t.act(0, pact, choices=[lions], then=[moves(pact, Zone.STACK, seat=0)])
    _resolve(t, then=[moves(pact, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.pass_to(Step.END, 1)
    t.pass_(1)
    t.pass_(0, then=[on_stack(SlaughterPactAbility2, 0)], note="the pact comes due at its caster's upkeep")
    t.pass_(0, choices=[Decision.no()], note="no mana to pay {2}{B}")
    t.pass_(1, then=[off_stack(SlaughterPactAbility2), wins(1)])
    t.run()
