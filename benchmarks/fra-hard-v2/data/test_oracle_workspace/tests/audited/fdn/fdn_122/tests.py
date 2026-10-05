"""Reference test for FDN 122 — Kykar, Zephyr Awakener.

"Whenever you cast a noncreature spell, choose one — Exile another target
creature you control. Return that card to the battlefield under its owner's
control at the beginning of the next end step. / Create a 1/1 white Spirit
creature token with flying."

Player 0 casts Burst Lightning at player 1 to trigger Kykar. The flickered
creature returns as a new object — it started tapped and comes back untapped.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_122.card_impl import (
    KykarZephyrAwakener,
    KykarZephyrAwakenerAbility2,
    KykarZephyrAwakenerAbility3,
    KykarZephyrAwakenerAbility4,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import (
    Decision,
    ManaType,
    Phase,
    PlayDiverged,
    Side,
    Step,
    Zone,
    card,
    create_game,
    player,
    token,
)

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

FLICKER = Decision.mode(printed=KykarZephyrAwakenerAbility3)
SPIRIT = Decision.mode(printed=KykarZephyrAwakenerAbility4)


def _table(lions, *, p1_battlefield=()):
    bolt = card(BurstLightning)
    game = create_game(
        Side(hand=[bolt], battlefield=[KykarZephyrAwakener, lions], library=[Forest], mana={ManaType.RED: 1}),
        Side(battlefield=list(p1_battlefield), library=[Forest]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), bolt


def _cast_and_trigger(t, bolt, choices, *, then):
    """Player 0 casts Burst Lightning at player 1; Kykar's trigger, answered
    with ``choices`` whenever its mode and target are asked, resolves with
    ``then``, and then the Burst Lightning resolves."""
    t.act(0, bolt, choices=[player(1), *choices], then=[moves(bolt, Zone.STACK), on_stack(KykarZephyrAwakenerAbility2, 0)])
    t.pass_(0, choices=choices)
    t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility2), *then])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])


class TestKykarProperties:
    """Static card data should match the FDN 122 spec."""

    def test_name(self) -> None:
        assert printed_class(KykarZephyrAwakener()) is KykarZephyrAwakener

    def test_mana_cost(self) -> None:
        assert KykarZephyrAwakener().mana_cost == ManaCost.parse("{2}{W}{U}")


class TestKykarFlicker:
    """Flicker mode: exile, then return at the next end step."""

    def test_flicker_exiles_then_returns_as_a_new_object(self) -> None:
        lions = card(SavannahLions, tapped=True)
        t, bolt = _table(lions)
        _cast_and_trigger(t, bolt, [FLICKER, lions], then=[moves(lions, Zone.EXILE)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.pass_(0)
        t.pass_(1, then=[on_stack(KykarZephyrAwakenerAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility3), moves(lions, Zone.BATTLEFIELD)],
                note="the Lions returns untapped: a new object")
        t.run()

    def test_unanswered_query_is_a_hard_failure_not_a_token(self) -> None:
        """Fault attribution: with no answer to the trigger's mode, play
        cannot go on — the engine never silently makes a token."""
        lions = card(SavannahLions)
        t, bolt = _table(lions)
        _cast_and_trigger(t, bolt, [], then=[])
        with pytest.raises(PlayDiverged, match="answers this question"):
            t.run()

    def test_token_mode_creates_spirit_and_no_flicker(self) -> None:
        lions = card(SavannahLions)
        t, bolt = _table(lions)
        _cast_and_trigger(t, bolt, [SPIRIT], then=[appears(0)])
        t.run()


class TestKykarSpiritToken:
    """The token leg mints a 1/1 Spirit creature token with flying."""

    def test_spirit_token_is_a_one_one_flier(self) -> None:
        """On player 0's next turn the Spirit attacks: Aegis Turtle cannot
        block it, and it deals 1."""
        lions, turtle = card(SavannahLions), card(AegisTurtle)
        t, bolt = _table(lions, p1_battlefield=[turtle])
        _cast_and_trigger(t, bolt, [SPIRIT], then=[appears(0)])
        t.pass_to(Step.UPKEEP, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        spirit = token(1)
        t.act(0, spirit, then=[taps(spirit)])
        t.pass_(0)
        t.pass_(1)
        t.act_illegal(1, turtle, scoped={turtle: spirit}, note="the Spirit flies")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)])
        t.run()
