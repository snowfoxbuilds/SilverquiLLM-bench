"""Printed characteristics, public protection behavior and the graveyard
replacement for Progenitus."""

from __future__ import annotations

from cards.fdn.fdn_60.card_impl import GutlessPlunderer
from cards.fdn.fdn_140.card_impl import DayOfJudgment
from cards.fdn.fdn_244.card_impl import Progenitus
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import printed_class
from engine.types import ManaCost, Supertype
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, shuffled

from silverquillm.table import Table, moves, taps


class TestProgenitusProperties:
    """Static card data should match the FDN 244 spec."""

    def test_name(self) -> None:
        assert printed_class(Progenitus(owner=None)) is Progenitus

    def test_mana_cost(self) -> None:
        cost = ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}")
        assert Progenitus(owner=None).mana_cost == cost

    def test_legendary_hydra_avatar(self) -> None:
        card = Progenitus(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Hydra", "Avatar"} <= card.subtypes


def test_protection_from_everything_prevents_damage():
    """Blocking a deathtouch attacker, Progenitus takes none of its damage and
    survives, while its own 10 damage kills the attacker."""
    progenitus, plunderer = card(Progenitus), card(GutlessPlunderer)
    game = create_game(
        Side(battlefield=[progenitus]),
        Side(battlefield=[plunderer]),
        start=(Step.BEGIN_COMBAT, 1),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, plunderer, then=[taps(plunderer)])
    t.pass_(1)
    t.pass_(0)
    t.act(0, progenitus, scoped={progenitus: plunderer})
    t.pass_(1)
    t.pass_(0, then=[moves(plunderer, Zone.GRAVEYARD)], note="deathtouch damage to Progenitus is prevented")
    t.run()


class TestProgenitusGraveyardReplacement:
    def test_replacement_redirects_to_library_and_prevents(self) -> None:
        """Destroyed, it is shuffled into its owner's library instead of going
        to the graveyard (rule 614.1a), and it leaves the battlefield."""
        progenitus, judgment, plains = card(Progenitus), card(DayOfJudgment), card(Plains)
        game = create_game(
            Side(
                hand=[judgment],
                battlefield=[progenitus],
                library=[plains],
                mana={ManaType.WHITE: 2, ManaType.COLORLESS: 2},
            ),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, judgment, then=[moves(judgment, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[moves(judgment, Zone.GRAVEYARD), moves(progenitus, Zone.LIBRARY)],
            note="Progenitus is shuffled into its owner's library instead of its graveyard",
        )
        t.run(chance=[shuffled(progenitus, plains)])
