"""Reference test for FDN 104 — Elvish Regrower.

The enters ability returns target *permanent* card (creature, artifact,
enchantment, land or planeswalker) from its controller's graveyard to their
hand; an instant card is never offered, and with no permanent card in the
graveyard the cast is refused.
"""

from __future__ import annotations

from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
from cards.fdn.fdn_92.card_impl import RiteOfTheDragoncaller
from cards.fdn.fdn_104.card_impl import ElvishRegrower, ElvishRegrowerAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_249.card_impl import AdventuringGear
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import ManaCost, ManaType, Phase, Zone
from test_interface import Side, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack

_MANA = {ManaType.GREEN: 2, ManaType.COLORLESS: 2}


def _regrower_game(graveyard):
    regrower = card(ElvishRegrower)
    game = create_game(
        Side(hand=[regrower], graveyard=list(graveyard), mana=_MANA), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
    )
    return Table(game), regrower


def _returns(dead):
    """The Regrower targets ``dead`` and returns it to hand."""
    t, regrower = _regrower_game([dead])
    t.act(0, regrower, then=[moves(regrower, Zone.STACK)])
    t.pass_(0, choices=[dead])
    t.pass_(1, then=[moves(regrower, Zone.BATTLEFIELD), on_stack(ElvishRegrowerAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ElvishRegrowerAbility1), moves(dead, Zone.HAND)])
    t.run()


def _no_target(graveyard, *, note):
    """The Regrower enters with no legal target, so its trigger is removed."""
    t, regrower = _regrower_game(graveyard)
    t.act(0, regrower, then=[moves(regrower, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(regrower, Zone.BATTLEFIELD)], note=note)
    t.run()


class TestElvishRegrowerProperties:
    def test_static_data(self):
        card = ElvishRegrower(owner=None)
        assert printed_class(card) is ElvishRegrower
        assert card.mana_cost == ManaCost.parse("{2}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 3)
        assert card.subtypes == {"Elf", "Druid"}


class TestElvishRegrowerETB:
    def test_returns_targeted_land_card_to_hand(self):
        _returns(card(Forest))

    def test_option_set_any_permanent_card_but_not_instant(self):
        for permanent in (SavannahLions, Forest, AdventuringGear, RiteOfTheDragoncaller, ChandraFlameshaper):
            _returns(card(permanent))
        _no_target([card(BurstLightning)], note="an instant card is not a permanent card")

    def test_no_legal_target_removes_the_trigger(self):
        """With no permanent card in its controller's graveyard, the Regrower
        still resolves, and its enters trigger, with no legal target, is
        removed from the stack (rule 603.3d)."""
        _no_target([], note="no trigger goes on the stack")
