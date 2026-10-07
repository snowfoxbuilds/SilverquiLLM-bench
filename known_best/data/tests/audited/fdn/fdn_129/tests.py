"""Leyline Axe attaches through paid equip activations and normal zone departures.

"Equipped creature gets +1/+1 and has double strike and trample. Equip {3}."
The buff shows in what damage does: an equipped Hungry Ghoul (2/2) is a 3/3
that survives Burst Lightning's 2 damage, and it attacks with double strike.
"""

from cards.fdn.fdn_62.card_impl import HungryGhoul
from cards.fdn.fdn_129.card_impl import LeylineAxe, LeylineAxeAbility3
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2, AbradeAbility3
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_226.card_impl import InspiringCall
from engine.card import Equipment, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, first_strike_damage, life, moves, off_stack, on_stack, taps

EQUIP = LeylineAxeAbility3


def _table(p0_hand=(), p0_battlefield=(), *, mana, p1=None, start=(Phase.PRECOMBAT_MAIN, 0)):
    game = create_game(
        Side(hand=list(p0_hand), battlefield=[LeylineAxe, *p0_battlefield], mana=mana),
        p1 or Side(),
        start=start,
    )
    return Table(game)


def _equip(t, target):
    t.act(0, EQUIP, choices=[target], then=[on_stack(EQUIP, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EQUIP)])


def _cast(t, spell, *choices, then=(), seat=0):
    t.act(seat, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(spell, Zone.GRAVEYARD), *then])


def test_static_data():
    card = LeylineAxe()
    assert printed_class(card) is LeylineAxe and card.mana_cost == ManaCost.parse("{4}")
    assert card.equip_cost == ManaCost.parse("{3}")


def test_is_equipment():
    card = LeylineAxe()
    assert isinstance(card, Equipment) and card.is_equipment
    assert "Equipment" in card.subtypes


def test_equip_buffs_then_equipment_departure_removes_buff():
    """Equipped, the Ghoul survives Burst Lightning; once Abrade destroys the
    Axe it is a 2/2 again, and the 2 damage marked on it is lethal."""
    ghoul, bolt, abrade = card(HungryGhoul), card(BurstLightning), card(Abrade)
    t = _table([bolt, abrade], [ghoul], mana={ManaType.RED: 6})
    _equip(t, ghoul)
    _cast(t, bolt, ghoul)
    _cast(t, abrade, AbradeAbility3, LeylineAxe, then=[moves(LeylineAxe, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.run()


def test_buff_moves_when_re_equipped():
    """Re-equipped from the first Ghoul to the second, the Axe buffs only the
    second: Burst Lightning kills the first and not the second, and the second
    attacks unblocked with double strike, dealing 3 twice."""
    first, second, bolt1, bolt2 = card(HungryGhoul), card(HungryGhoul), card(BurstLightning), card(BurstLightning)
    t = _table([bolt1, bolt2], [first, second], mana={ManaType.RED: 8})
    _equip(t, first)
    _equip(t, second)
    _cast(t, bolt1, first, then=[moves(first, Zone.GRAVEYARD)])
    _cast(t, bolt2, second)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, second, then=[taps(second)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1, then=[first_strike_damage()])
    t.pass_(0)
    t.pass_(1, then=[life(1, 17)])
    t.pass_(0)
    t.pass_(1, then=[life(1, 14)])
    t.run()


def test_creature_death_detaches_equipment():
    """The equipped Ghoul dies to Abrade; the Axe stays on the battlefield,
    unattached, and equips the second Ghoul, which then survives Burst
    Lightning."""
    ghoul, other, abrade, bolt = card(HungryGhoul), card(HungryGhoul), card(Abrade), card(BurstLightning)
    t = _table([abrade, bolt], [ghoul, other], mana={ManaType.RED: 9})
    _equip(t, ghoul)
    _cast(t, abrade, AbradeAbility2, ghoul, then=[moves(ghoul, Zone.GRAVEYARD)])
    _equip(t, other)
    _cast(t, bolt, other)
    t.run()


def test_equip_only_at_sorcery_speed():
    """In the beginning of combat step equip cannot be activated, and the
    three mana stay to cast Inspiring Call."""
    ghoul, call = card(HungryGhoul), card(InspiringCall)
    t = _table([call], [ghoul], mana={ManaType.GREEN: 3}, start=(Step.BEGIN_COMBAT, 0))
    t.act_illegal(0, EQUIP, choices=[ghoul], note="not a main phase")
    _cast(t, call)
    t.run()


def test_equip_no_legal_target_spends_no_mana():
    """Only player 1 controls a creature, so equip cannot be activated; the
    three mana stay to cast Inspiring Call."""
    theirs, call = card(HungryGhoul), card(InspiringCall)
    t = _table([call], mana={ManaType.GREEN: 3}, p1=Side(battlefield=[theirs]))
    t.act_illegal(0, EQUIP, choices=[theirs], note="equip targets only a creature you control")
    _cast(t, call)
    t.run()


def test_equip_pays_before_attachment_resolves():
    """Equip's {3} is paid on activation — Inspiring Call can no longer be
    cast — and the Axe attaches only on resolution: Burst Lightning in
    response still kills the 2/2 Ghoul."""
    ghoul, call, bolt = card(HungryGhoul), card(InspiringCall), card(BurstLightning)
    t = _table([call], [ghoul], mana={ManaType.GREEN: 3},
               p1=Side(hand=[bolt], mana={ManaType.RED: 1}))
    t.act(0, EQUIP, choices=[ghoul], then=[on_stack(EQUIP, 0)])
    t.act_illegal(0, call, note="the mana is spent")
    t.pass_(0)
    t.act(1, bolt, choices=[ghoul], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EQUIP)])
    t.run()
