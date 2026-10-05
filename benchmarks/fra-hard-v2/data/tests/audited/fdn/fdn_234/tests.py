"""Audited tests for FDN 234 — Vivien Reid.

"+1: Look at the top four cards of your library. You may reveal a creature
or land card from among them and put it into your hand. Put the rest on the
bottom of your library in a random order. −3: Destroy target artifact,
enchantment, or creature with flying." The −3 target is chosen at
activation, only among permanents matching that filter; with none, the
ability cannot be activated and no loyalty is spent, so Vivien may still
activate +1 that turn. After a −3 her 2 loyalty cannot pay another −3.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_52.card_impl import StrixLookout
from cards.fdn.fdn_116.card_impl import AnthemOfChampions
from cards.fdn.fdn_130.card_impl import QuickDrawKatana
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_234.card_impl import VivienReid, VivienReidAbility1, VivienReidAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from engine.abilities import clear_loyalty_tracking
from engine.card import printed_class
from engine.types import ManaCost, Supertype
from test_interface import Phase, Side, Zone, card, create_game, shuffled

from silverquillm.table import Table, moves, off_stack, on_stack


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _table(theirs=(), *, library=(), their_library=()):
    game = create_game(
        Side(battlefield=[VivienReid], library=list(library)),
        Side(battlefield=list(theirs), library=list(their_library)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _minus_three(t, target):
    t.act(0, VivienReidAbility2, choices=[target], then=[on_stack(VivienReidAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(VivienReidAbility2), moves(target, Zone.GRAVEYARD)])


def _plus_one(t, plains, forest, mountain):
    """Vivien's +1 over a library of Plains, Forest and Mountain: player 0
    puts the Plains into hand, and the other two go to the bottom in the
    order the chance script gives."""
    t.act(0, VivienReidAbility1, then=[on_stack(VivienReidAbility1, 0)])
    t.pass_(0, choices=[plains])
    t.pass_(1, then=[
        off_stack(VivienReidAbility1), moves(plains, Zone.HAND),
        moves(forest, Zone.LIBRARY, bottom=True), moves(mountain, Zone.LIBRARY, bottom=True),
    ])


class TestVivienProperties:
    def test_static_data(self):
        vivien = VivienReid(owner=None)
        assert printed_class(vivien) is VivienReid
        assert vivien.mana_cost == ManaCost.parse("{3}{G}{G}")
        assert vivien.starting_loyalty == 5
        assert Supertype.LEGENDARY in vivien.supertypes
        assert "Vivien" in vivien.subtypes


class TestVivienMinusThree:
    def test_destroys_flying_creature(self):
        """−3 destroys a flier; on player 0's next turn Vivien, at 2 loyalty,
        cannot −3 the other one."""
        flyer, other_flyer = card(StrixLookout), card(StrixLookout)
        t = _table([flyer, other_flyer], library=[Plains], their_library=[Plains])
        _minus_three(t, flyer)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act_illegal(0, VivienReidAbility2, choices=[other_flyer], note="2 loyalty cannot pay −3")
        t.pass_(0)
        t.run()

    def test_destroys_artifact(self):
        katana = card(QuickDrawKatana)
        t = _table([katana])
        _minus_three(t, katana)
        t.run()

    def test_destroys_enchantment(self):
        anthem = card(AnthemOfChampions)
        t = _table([anthem])
        _minus_three(t, anthem)
        t.run()

    def test_ground_creature_is_not_a_legal_target(self):
        """With only a non-flying creature, −3 cannot be activated; no loyalty
        ability was activated, so Vivien may still +1 this turn."""
        lions = card(SavannahLions)
        plains, forest, mountain = card(Plains), card(Forest), card(Mountain)
        t = _table([lions], library=[plains, forest, mountain])
        t.act_illegal(0, VivienReidAbility2, choices=[lions])
        _plus_one(t, plains, forest, mountain)
        t.run(chance=[shuffled(forest, mountain)])

    def test_no_legal_target_rejected_before_cost(self):
        t = _table()
        t.act_illegal(0, VivienReidAbility2)
        t.pass_(0)
        t.run()


class TestVivienUntargeted:
    def test_plus_one_activates_and_resolves(self):
        plains, forest, mountain = card(Plains), card(Forest), card(Mountain)
        t = _table(library=[plains, forest, mountain])
        _plus_one(t, plains, forest, mountain)
        t.run(chance=[shuffled(forest, mountain)])
