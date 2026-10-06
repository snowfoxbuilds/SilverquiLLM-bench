"""Reference test for FDN 139 — Cathar Commando.

Demonstrates a **targeted activated ability** (Phase D pattern 2) whose cost
sacrifices the source. The artifact/enchantment target is chosen at activation
(before the sacrifice), captured on the stack, revalidated at resolution, and
destroyed. The tests play it at the table: player 0 taps a Plains for the {1}
and activates Cathar Commando, and what player 1's permanents do shows the
result.
"""

from __future__ import annotations

from cards.fdn.fdn_131.card_impl import RavenousAmulet
from cards.fdn.fdn_139.card_impl import CatharCommando, CatharCommandoAbility2
from cards.fdn.fdn_142.card_impl import HealersHawk
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_180.card_impl import PhyrexianArena
from cards.fdn.fdn_254.card_impl import HeraldicBanner
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import printed_class
from engine.types import Keyword, ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack, taps


class TestCatharCommandoProperties:
    def test_static_data(self):
        card = CatharCommando(owner=None)
        assert printed_class(card) is CatharCommando
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert (card.base_power, card.base_toughness) == (3, 1)
        assert {"Human", "Soldier"} <= card.subtypes
        assert Keyword.FLASH in card.keywords


def _table(*opposing, hand=()):
    """Player 0's main phase: Cathar Commando and a Plains against
    ``opposing`` permanents of player 1."""
    cathar, plains = card(CatharCommando), card(Plains)
    game = create_game(
        Side(battlefield=[cathar, plains], hand=list(hand)),
        Side(battlefield=list(opposing)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), cathar, plains


def _activate(t, cathar, plains, target):
    """Player 0 taps the Plains and activates Cathar Commando at ``target``;
    the sacrifice is paid as it is activated."""
    t.act(0, plains, then=[taps(plains)])
    t.act(0, CatharCommandoAbility2, choices=[target], then=[moves(cathar, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 0)])


class TestCatharCommandoAbility:
    def test_destroys_target_artifact(self):
        amulet = card(RavenousAmulet)
        t, cathar, plains = _table(amulet)
        _activate(t, cathar, plains, amulet)
        t.pass_(0)
        t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(amulet, Zone.GRAVEYARD)])
        t.run()

    def test_source_is_sacrificed_as_cost(self):
        """Cathar Commando is in the graveyard while its ability waits on the
        stack, and the Plains' mana went to the {1}: once the ability has
        resolved, still in the main phase, nothing is left for Healer's
        Hawk."""
        amulet, hawk = card(RavenousAmulet), card(HealersHawk)
        t, cathar, plains = _table(amulet, hand=[hawk])
        _activate(t, cathar, plains, amulet)
        t.pass_(0)
        t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(amulet, Zone.GRAVEYARD)])
        t.act_illegal(0, hawk, note="the {1} was paid, so no mana is left")
        t.run()

    def test_target_captured_on_stack(self):
        """With two artifacts, the one chosen at activation is the one destroyed."""
        amulet, banner = card(RavenousAmulet), card(HeraldicBanner)
        t, cathar, plains = _table(amulet, banner)
        _activate(t, cathar, plains, banner)
        t.pass_(0)
        t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(banner, Zone.GRAVEYARD)])
        t.run()

    def test_can_target_enchantment(self):
        arena = card(PhyrexianArena)
        t, cathar, plains = _table(arena)
        _activate(t, cathar, plains, arena)
        t.pass_(0)
        t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(arena, Zone.GRAVEYARD)])
        t.run()

    def test_no_legal_target_rejected_before_cost(self):
        """Option-set invariant: only artifacts/enchantments are legal targets.
        With only a creature present there is no legal target, so activation is
        rejected before any cost: Cathar Commando stays, and the pool's {W}
        still casts Healer's Hawk."""
        lions, hawk = card(SavannahLions), card(HealersHawk)
        cathar = card(CatharCommando)
        game = create_game(
            Side(battlefield=[cathar], hand=[hawk], mana={ManaType.WHITE: 1}),
            Side(battlefield=[lions]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act_illegal(0, cathar, choices=[lions])
        t.act(0, hawk, then=[moves(hawk, Zone.STACK)], note="the {W} is still in the pool")
        t.pass_(0)
        t.pass_(1, then=[moves(hawk, Zone.BATTLEFIELD)])
        t.run()
