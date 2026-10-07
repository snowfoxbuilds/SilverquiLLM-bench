"""Reference test for FDN 188 — Abrade.

Pattern 5 — modal spell ("choose one —"). The mode is chosen as Abrade is
cast (a real MODE Player Query); the chosen mode selects which target is
legal, so mode 0 targets a creature and mode 1 targets an artifact. The
caster's script answers both the mode and the target, naming the mode by its
printed class.
"""

from __future__ import annotations

from cards.fdn.fdn_114.card_impl import TreetopSnarespinner
from cards.fdn.fdn_131.card_impl import RavenousAmulet
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2, AbradeAbility3
from cards.fdn.fdn_191.card_impl import BrazenScourge
from engine.card import printed_class
from engine.types import ManaCost, ManaType, Phase, Zone
from test_interface import Side, card, create_game

from table import Table, moves


def _abrade(choices, *opposing, then, fallback=None):
    """Player 0 casts Abrade from {R}{R} answering ``choices`` — its mode,
    then its target — at player 1's ``opposing`` permanents; ``fallback``
    answers the recast when the engine offers ``choices``' target and
    rejects it."""
    abrade = card(Abrade)
    game = create_game(
        Side(hand=[abrade], mana={ManaType.RED: 2}),
        Side(battlefield=list(opposing)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    branches = [[abrade, *choices]] + ([[abrade, *fallback]] if fallback else [])
    t.act(0, branches=branches, then=[moves(abrade, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(abrade, Zone.GRAVEYARD), *then])
    t.run()


class TestAbradeProperties:
    def test_static_data(self):
        abrade = Abrade(owner=None)
        assert printed_class(abrade) is Abrade
        assert abrade.mana_cost == ManaCost.parse("{1}{R}")


class TestAbradeDamageMode:
    def test_deals_3_damage_and_kills(self):
        scourge = card(BrazenScourge)
        _abrade([AbradeAbility2, scourge], scourge, then=[moves(scourge, Zone.GRAVEYARD)])

    def test_deals_exactly_3_damage(self):
        """A 1/4 survives the 3 damage (a 3/3 does not, above)."""
        spider = card(TreetopSnarespinner)
        _abrade([AbradeAbility2, spider], spider, then=[])

    def test_damage_mode_offers_only_creatures(self):
        """Mode 0 targets creatures only: preferring the artifact, the target is
        still the creature, whether the engine never offers the artifact or
        offers it and rejects it, the cast then retried at the creature."""
        lions, amulet = card(SavannahLions), card(RavenousAmulet)
        _abrade([AbradeAbility2, amulet, lions], lions, amulet, then=[moves(lions, Zone.GRAVEYARD)],
                fallback=[AbradeAbility2, lions])


class TestAbradeDestroyArtifactMode:
    def test_destroys_target_artifact(self):
        amulet = card(RavenousAmulet)
        _abrade([AbradeAbility3, amulet], amulet, then=[moves(amulet, Zone.GRAVEYARD)])

    def test_destroy_mode_offers_only_artifacts(self):
        """Mode 1 targets artifacts only: preferring the plain creature, the
        target is still the artifact, whether the engine never offers the
        creature or offers it and rejects it."""
        lions, amulet = card(SavannahLions), card(RavenousAmulet)
        _abrade([AbradeAbility3, lions, amulet], lions, amulet, then=[moves(amulet, Zone.GRAVEYARD)],
                fallback=[AbradeAbility3, amulet])
