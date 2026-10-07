"""Regression tests for FDN 165 — Think Twice.

Think Twice is an instant with Flashback {2}{U}. The behavioural surface
Phase G (cadence alignment) fixes is its post-resolution zone: when cast
normally it goes to the graveyard, but when cast via **flashback** (from the
graveyard) it is exiled as it resolves (rule 702.34e) rather than returning to
the graveyard — which is what the GRE stream shows (graveyard -> exile), not a
graveyard round-trip. Both casts still resolve their "draw a card" effect.
"""

from __future__ import annotations

from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_194.card_impl import EtaliPrimalStorm, EtaliPrimalStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from engine.card import Instant
from engine.types import ManaCost, Zone
from test_interface import Decision, ManaType, Phase, Side, Step, card, create_game

from table import Table, moves, off_stack, on_stack, taps


class TestThinkTwiceProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ThinkTwice(owner=None), Instant)

    def test_flashback_cost(self) -> None:
        assert ThinkTwice(owner=None).flashback_cost == ManaCost.parse("{2}{U}")


class TestThinkTwiceFlashbackExile:
    @staticmethod
    def _flashback():
        """Player 0 casts Think Twice from the graveyard for {2}{U}; it draws
        the Island and is exiled."""
        think, drawn = card(ThinkTwice), card(Island)
        game = create_game(
            Side(graveyard=[think], library=[drawn], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(drawn, Zone.HAND), moves(think, Zone.EXILE)])
        return t

    def test_flashback_cast_exiles_on_resolution(self) -> None:
        self._flashback().run()

    def test_flashback_cast_still_draws(self) -> None:
        self._flashback().run()

    def test_normal_resolution_goes_to_graveyard(self) -> None:
        """The disposition override is flashback-only: Think Twice cast for
        free from exile (by Etali, Primal Storm's attack trigger) draws and
        goes to the graveyard, never a silent exile."""
        etali, think, drawn = card(EtaliPrimalStorm), card(ThinkTwice), card(Island)
        p1_top = card(Plains)
        game = create_game(
            Side(battlefield=[etali], library=[think, drawn]),
            Side(library=[p1_top]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, etali, then=[taps(etali), on_stack(EtaliPrimalStormAbility1, 0)])
        t.pass_(0, choices=[Decision.yes(), think])
        t.pass_(
            1,
            then=[off_stack(EtaliPrimalStormAbility1), moves(think, Zone.STACK, seat=0), moves(p1_top, Zone.EXILE)],
        )
        t.pass_(0)
        t.pass_(1, then=[moves(drawn, Zone.HAND), moves(think, Zone.GRAVEYARD)])
        t.run()
