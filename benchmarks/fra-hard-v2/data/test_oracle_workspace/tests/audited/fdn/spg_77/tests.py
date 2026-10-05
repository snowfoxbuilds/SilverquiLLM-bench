"""Embercleave's attacking discount, paid equip and entry attachment are observable.

The equipped creature gets +1/+1 and double strike, so an equipped Savannah
Lions deals 6 combat damage where an unequipped one deals 2.
"""

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.spg_77.card_impl import Embercleave, EmbercleaveAbility3, EmbercleaveAbility5
from engine.card import Equipment, printed_class
from engine.types import Keyword, ManaCost, Supertype
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, first_strike_damage, life, moves, off_stack, on_stack, taps


def _cast_cleave(t: Table, cleave, onto) -> None:
    """Player 0 casts Embercleave; its enters trigger, targeting ``onto``
    (rule 603.3d), attaches it."""
    t.act(0, cleave, then=[moves(cleave, Zone.STACK)])
    t.pass_(0, choices=[onto])
    t.pass_(1, then=[moves(cleave, Zone.BATTLEFIELD), on_stack(EmbercleaveAbility3, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EmbercleaveAbility3)])


def _combat_damage(t: Table, first: int, total: int) -> None:
    """No blocks; the equipped creature's double strike adds a first-strike
    combat damage step (rule 510.4), after which player 1's life is
    ``first``, and ``total`` after the regular one."""
    t.pass_(0)
    t.pass_(1)
    t.pass_(1, then=[first_strike_damage()])
    t.pass_(0)
    t.pass_(1, then=[life(1, first)])
    t.pass_(0)
    t.pass_(1, then=[life(1, total)])


def _declare(t: Table, *attackers) -> None:
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, *attackers, then=[taps(a) for a in attackers])


def test_static_data():
    card = Embercleave()
    assert printed_class(card) is Embercleave and card.mana_cost == ManaCost.parse("{4}{R}{R}")
    assert card.equip_cost == ManaCost.parse("{3}")
    assert Supertype.LEGENDARY in card.supertypes and card.keywords & Keyword.FLASH
    assert isinstance(card, Equipment) and card.is_equipment


def test_cost_reduction_per_attacking_creature():
    """With two attackers, four lands pay for Embercleave."""
    first, second, cleave = card(SavannahLions), card(SavannahLions), card(Embercleave)
    lands = [card(Mountain), card(Mountain), card(Plains), card(Plains)]
    game = create_game(
        Side(hand=[cleave], battlefield=[first, second, *lands]),
        Side(),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    _declare(t, first, second)
    for land in lands:
        t.act(0, land, then=[taps(land)])
    _cast_cleave(t, cleave, first)
    _combat_damage(t, 17, 12)
    t.run()


def test_static_buff_after_paid_equip():
    lions, cleave = card(SavannahLions), card(Embercleave)
    game = create_game(
        Side(battlefield=[lions, cleave], mana={ManaType.COLORLESS: 3}),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, EmbercleaveAbility5, choices=[lions], then=[on_stack(EmbercleaveAbility5, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EmbercleaveAbility5)])
    _declare(t, lions)
    _combat_damage(t, 17, 14)
    t.run()


def test_cast_entry_attaches_to_the_chosen_creature():
    other, chosen, cleave = card(SavannahLions), card(SavannahLions), card(Embercleave)
    game = create_game(
        Side(hand=[cleave], battlefield=[other, chosen], mana={ManaType.RED: 6}),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    _cast_cleave(t, cleave, chosen)
    _declare(t, other, chosen)
    _combat_damage(t, 17, 12)
    t.run()
