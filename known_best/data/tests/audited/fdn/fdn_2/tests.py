"""Audited tests for FDN 2 — Arahbo, the First Fang.

"Other Cats you control get +1/+1. Whenever Arahbo or another nontoken Cat you
control enters, create a 1/1 white Cat creature token."

Arahbo's own entry makes exactly one Cat, another nontoken Cat entering makes
one more, and the Cat token entering makes none. What the token is shows in
combat: a 1/1 that Arahbo makes bigger.
"""

from __future__ import annotations

from cards.fdn.fdn_2.card_impl import ArahboTheFirstFang, ArahboTheFirstFangAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, off_stack, on_stack, taps

_ARAHBO_MANA = {ManaType.WHITE: 1, ManaType.COLORLESS: 2}


def _cast_arahbo(**p0):
    """Turn 1: player 0 casts Arahbo, and its trigger for its own entry
    resolves."""
    arahbo = card(ArahboTheFirstFang)
    hand = [arahbo, *p0.pop("hand", ())]
    game = create_game(
        Side(hand=hand, mana=_ARAHBO_MANA, library=[card(Plains)], **p0),
        Side(library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, arahbo, then=[moves(arahbo, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(arahbo, Zone.BATTLEFIELD), on_stack(ArahboTheFirstFangAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ArahboTheFirstFangAbility2), appears(0)])
    return t, arahbo


def _cat_attacks_alone(t, damage_to=None):
    """Player 0's next turn: the Cat token attacks and is not blocked."""
    t.pass_to(Step.UPKEEP, 0)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, token(1), then=[taps(token(1))])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[damage_to] if damage_to else [])


class TestArahboSelfETB:
    def test_own_entry_mints_exactly_one_cat(self) -> None:
        t, _arahbo = _cast_arahbo()
        t.run()

    def test_minted_cat_has_spec_characteristics(self) -> None:
        """With Arahbo gone, the token attacks as the 1/1 it was made."""
        mountain, bolt = card(Mountain), card(BurstLightning)
        t, arahbo = _cast_arahbo(hand=[bolt], battlefield=[mountain])
        t.act(0, mountain, then=[taps(mountain)])
        t.act(0, bolt, choices=[arahbo], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(arahbo, Zone.GRAVEYARD)])
        _cat_attacks_alone(t, life(1, 19))
        t.run()

    def test_minted_cat_is_a_cat_arahbo_pumps(self) -> None:
        """Arahbo's "other Cats" boost makes the 1/1 Cat token hit for 2."""
        t, _arahbo = _cast_arahbo()
        _cat_attacks_alone(t, life(1, 18))
        t.run()

    def test_another_nontoken_cat_mints_but_a_cat_token_does_not(self):
        lions = card(SavannahLions)
        game = create_game(
            Side(hand=[lions], battlefield=[ArahboTheFirstFang], mana={ManaType.WHITE: 1}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD), on_stack(ArahboTheFirstFangAbility2, 0)])
        t.pass_(0)
        t.pass_(
            1,
            then=[off_stack(ArahboTheFirstFangAbility2), appears(0)],
            note="the Cat token entering puts no trigger on the stack",
        )
        t.run()
