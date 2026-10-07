"""Audited tests for FDN 94 — Slumbering Cerberus.

"This creature doesn't untap during your untap step. Morbid — At the beginning
of each end step, if a creature died this turn, untap this creature." Each
test plays a real death or its absence, then the end step (rules 502.3,
700.4).
"""

from cards.fdn.fdn_94.card_impl import SlumberingCerberus, SlumberingCerberusAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Step, Zone, card, create_game

from table import Table, moves, off_stack, on_stack, stays_tapped, untaps


class TestSlumberingCerberusProperties:
    def test_static_data(self):
        card = SlumberingCerberus(owner=None)
        assert printed_class(card) is SlumberingCerberus
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (4, 2)
        assert "Dog" in card.subtypes


class TestSlumberingCerberusMorbid:
    def test_untaps_when_a_creature_died_this_turn(self):
        cerberus, bolt, lions = card(SlumberingCerberus, tapped=True), card(BurstLightning), card(SavannahLions)
        game = create_game(
            Side(hand=[bolt], battlefield=[cerberus], mana={ManaType.RED: 1}),
            Side(battlefield=[lions]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.pass_(0)
        t.pass_(1, then=[on_stack(SlumberingCerberusAbility2, 0)], note="a creature died this turn")
        t.pass_(0)
        t.pass_(1, then=[off_stack(SlumberingCerberusAbility2), untaps(cerberus)])
        t.run()

    def test_stays_tapped_when_no_creature_died(self):
        """No end step untaps it, and neither does its controller's next
        untap step."""
        cerberus = card(SlumberingCerberus, tapped=True)
        game = create_game(
            Side(battlefield=[cerberus], library=[card(Mountain)]),
            Side(library=[card(Mountain)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.pass_to(Step.END, 1)
        t.pass_(1)
        t.pass_(0, then=[stays_tapped(cerberus)], note="Cerberus doesn't untap in its untap step")
        t.run()
