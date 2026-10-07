"""Audited tests for FDN 201 — Heartfire Immolator.

"{R}, Sacrifice this creature: It deals damage equal to its power
to target creature or planeswalker." The target is chosen and the cost paid
as the ability is activated (rule 602.2); the sacrificed Immolator's power
is read as it last existed on the battlefield (rule 608.2h), so a boost it
had then still counts.
"""

from __future__ import annotations

from cards.fdn.fdn_116.card_impl import AnthemOfChampions
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_201.card_impl import (
    HeartfireImmolator,
    HeartfireImmolatorAbility2,
)
from cards.fdn.fdn_234.card_impl import VivienReid
from cards.fdn.fdn_250.card_impl import BurnishedHart
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack


def _table(mine, theirs):
    game = create_game(
        Side(battlefield=list(mine), mana={ManaType.RED: 1}),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _activate(t, immolator, target, *, then=()):
    """Player 0 pays {R} and sacrifices the Immolator at ``target``, and both
    players pass, resolving the ability. The ability is chosen by its class:
    the Immolator itself is a legal target."""
    t.act(0, HeartfireImmolatorAbility2, choices=[target],
          then=[moves(immolator, Zone.GRAVEYARD), on_stack(HeartfireImmolatorAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(HeartfireImmolatorAbility2), *then])


class TestHeartfireImmolatorProperties:
    def test_static_data(self):
        card = HeartfireImmolator(owner=None)
        assert printed_class(card) is HeartfireImmolator
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert {"Human", "Wizard"} <= card.subtypes
        assert Keyword.PROWESS in card.keywords


class TestHeartfireImmolatorAbility:
    def test_deals_damage_equal_to_power(self):
        """The 2-power Immolator kills a 2/2."""
        immolator, hart = card(HeartfireImmolator), card(BurnishedHart)
        t = _table([immolator], [hart])
        _activate(t, immolator, hart, then=[moves(hart, Zone.GRAVEYARD)])
        t.run()

    def test_damage_uses_power_snapshot_at_activation(self):
        """Anthem of Champions makes the Immolator 3/3; sacrificed, it is no
        longer pumped, yet it deals the 3 damage it had as it last existed:
        the 3/3 dies, which 2 damage would not kill."""
        immolator, scourge = card(HeartfireImmolator), card(BrazenScourge)
        t = _table([immolator, card(AnthemOfChampions)], [scourge])
        _activate(t, immolator, scourge, then=[moves(scourge, Zone.GRAVEYARD)])
        t.run()

    def test_target_captured_on_stack(self):
        """The creature chosen at activation is the one dealt damage."""
        immolator, first, second = card(HeartfireImmolator), card(BurnishedHart), card(BurnishedHart)
        t = _table([immolator], [first, second])
        _activate(t, immolator, second, then=[moves(second, Zone.GRAVEYARD)])
        t.run()

    def test_planeswalker_is_a_legal_target(self):
        """A planeswalker is a legal target. Player 0's Lions makes the target
        question one an engine could not fill in by itself."""
        immolator, walker = card(HeartfireImmolator), card(VivienReid)
        t = _table([immolator, card(SavannahLions)], [walker])
        _activate(t, immolator, walker)
        t.run()

    def test_source_off_battlefield_rejected_before_cost(self):
        """An Immolator in the graveyard cannot activate its ability."""
        immolator, hart = card(HeartfireImmolator), card(BurnishedHart)
        game = create_game(
            Side(graveyard=[immolator], mana={ManaType.RED: 1}),
            Side(battlefield=[hart]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act_illegal(0, immolator, choices=[hart])
        t.pass_(0)
        t.run()
