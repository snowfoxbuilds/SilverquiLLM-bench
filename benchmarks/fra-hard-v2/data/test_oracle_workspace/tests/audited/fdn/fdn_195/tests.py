"""Audited tests for FDN 195 — Fanatical Firebrand.

"{T}, Sacrifice this creature: It deals 1 damage to any target." The target
is chosen as the ability is activated and the cost is paid then (rule
602.2), so the Firebrand is in the graveyard while the ability waits; a
tapped Firebrand, or one off the battlefield, cannot activate it.
"""

from __future__ import annotations

from cards.fdn.fdn_195.card_impl import FanaticalFirebrand, FanaticalFirebrandAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import Phase, Side, Zone, card, create_game, player

from silverquillm.table import Table, life, moves, off_stack, on_stack


def _table(brand, *elves):
    game = create_game(
        Side(battlefield=[brand]),
        Side(battlefield=list(elves)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _activate(t, brand, target, *, then=()):
    """Player 0 activates the Firebrand at ``target``, sacrificing it, and both
    players pass, resolving the ability."""
    # The ability is chosen by its class: the Firebrand itself is "any target".
    t.act(0, FanaticalFirebrandAbility2, choices=[target], then=[moves(brand, Zone.GRAVEYARD), on_stack(FanaticalFirebrandAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(FanaticalFirebrandAbility2), *then])


class TestFanaticalFirebrandProperties:
    def test_static_data(self):
        card = FanaticalFirebrand(owner=None)
        assert printed_class(card) is FanaticalFirebrand
        assert card.mana_cost == ManaCost.parse("{R}")
        assert (card.base_power, card.base_toughness) == (1, 1)
        assert {"Goblin", "Pirate"} <= card.subtypes
        assert Keyword.HASTE in card.keywords


class TestFanaticalFirebrandAbility:
    def test_deals_damage_to_target_creature(self):
        brand, elves = card(FanaticalFirebrand), card(LlanowarElves)
        t = _table(brand, elves)
        _activate(t, brand, elves, then=[moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_deals_damage_to_a_player(self):
        """"Any target" includes players."""
        brand = card(FanaticalFirebrand)
        t = _table(brand, card(LlanowarElves))
        _activate(t, brand, player(1), then=[life(1, 19)])
        t.run()

    def test_cost_taps_and_sacrifices(self):
        """{T} is part of the cost: a tapped Firebrand cannot pay it, an
        untapped one is sacrificed as it is activated."""
        tapped, brand, elves = card(FanaticalFirebrand, tapped=True), card(FanaticalFirebrand), card(LlanowarElves)
        game = create_game(
            Side(battlefield=[tapped, brand]), Side(battlefield=[elves]), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act_illegal(0, tapped, choices=[elves], note="a tapped Firebrand cannot pay {T}")
        _activate(t, brand, elves, then=[moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_target_captured_on_stack(self):
        """The target chosen at activation is the one dealt damage."""
        brand, first, second = card(FanaticalFirebrand), card(LlanowarElves), card(LlanowarElves)
        t = _table(brand, first, second)
        _activate(t, brand, second, then=[moves(second, Zone.GRAVEYARD)])
        t.run()

    def test_source_off_battlefield_rejected_before_cost(self):
        """A Firebrand in the graveyard cannot activate its ability."""
        brand, elves = card(FanaticalFirebrand), card(LlanowarElves)
        game = create_game(Side(graveyard=[brand]), Side(battlefield=[elves]), start=(Phase.PRECOMBAT_MAIN, 0))
        t = Table(game)
        t.act_illegal(0, brand, choices=[elves])
        t.pass_(0)
        t.run()
