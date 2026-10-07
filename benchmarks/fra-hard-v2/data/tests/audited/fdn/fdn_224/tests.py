"""Audited tests for FDN 224 — Gnarlid Colony.

"Kicker {2}{G}. If this creature was kicked, it enters with two +1/+1
counters on it. Each creature you control with a +1/+1 counter on it has
trample." Unkicked it is a 2/2.

Known-Best offers no way to pay kicker and never applies the trample grant
(#169), so those are guarded by the Known-Best platform checks instead.
"""

from __future__ import annotations

from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_224.card_impl import GnarlidColony
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import printed_class
from engine.continuous_effects import Layer
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, moves, taps


class TestGnarlidColonyProperties:
    def test_name_and_cost(self) -> None:
        card = GnarlidColony(owner=None)
        assert printed_class(card) is GnarlidColony
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert (card.base_power, card.base_toughness) == (2, 2)


class TestGnarlidColonyKickerEntry:
    """Kicker: enters with two +1/+1 counters if it was kicked (rule 614.1c)."""

    def test_unkicked_enters_as_two_two(self) -> None:
        """Cast without kicker, the Colony blocks a 3/3 and dies without
        killing it."""
        colony, scourge = card(GnarlidColony), card(BrazenScourge)
        game = create_game(
            Side(hand=[colony], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1}),
            Side(battlefield=[scourge], library=[Plains]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, colony, then=[moves(colony, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(colony, Zone.BATTLEFIELD)])
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, scourge, then=[taps(scourge)])
        t.pass_(1)
        t.pass_(0)
        t.act(0, colony, scoped={colony: scourge})
        t.pass_(1)
        t.pass_(0, then=[moves(colony, Zone.GRAVEYARD)])
        t.run()


class TestGnarlidColonyContinuousEffect:
    """The previously-crashing get_continuous_effects path."""

    def test_effect_constructs_at_ability_layer(self) -> None:
        card = GnarlidColony(owner=None)
        effects = card.get_continuous_effects()  # must not raise
        assert len(effects) == 1
        assert effects[0].layer is Layer.ABILITY
        assert effects[0].sublayer is None
