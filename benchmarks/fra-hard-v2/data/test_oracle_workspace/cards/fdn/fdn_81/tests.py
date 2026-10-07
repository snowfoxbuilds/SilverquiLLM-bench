"""Reference test for FDN 81 — Chandra, Flameshaper.

Illustrative test covering the **−4 "divided as you choose" damage split**:
the split is a player choice re-expressed as NUMBER Player Queries (one per
target except the last, which takes the forced remainder), never a hardcoded
distribution. A baseline answer takes the first-offered (lowest) number; a
card intent picks the split via a ``Decision.number`` preference.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
from engine.abilities import clear_loyalty_tracking
from engine.card import Creature, Planeswalker, printed_class
from engine.decisions import Decision, DecisionKind, GameRef
from test_utils import Intent
from engine.types import ManaCost, Phase, Zone
from test_utils import (
    activate_loyalty_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    """The once-per-turn tracker is module-level — reset around every test."""
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _setup_minus4(game, n_targets):
    """Chandra on p1's battlefield in p1's main phase, with ``n_targets``
    creatures on p2's side to divide the damage among."""
    p1, p2 = game.players[0], game.players[1]
    pw = ChandraFlameshaper(owner=p1, controller=p1)
    targets = [
        Creature(name=f"Target{i}", base_power=4, base_toughness=9, owner=p2, controller=p2)
        for i in range(n_targets)
    ]
    set_board_state(game, 0, battlefield=[pw])
    set_board_state(game, 1, battlefield=targets)
    game.active_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    return pw, targets


def _minus4(game, player, pw, targets, numbers=()):
    """Activate −4 through the real activation path: the targets and the
    division are chosen as it is activated (rules 601.2c–d via 602.2b)."""
    player.set_baseline(Intent(pattern=GameRef(), preferences=()))
    player.start_intent("split", Intent(
        pattern=GameRef(card=frozenset({("printed", ChandraFlameshaper)})),
        preferences=(
            *(Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value)) for t in targets),
            *(Decision.number(n) for n in numbers),
        ),
    ))
    try:
        activate_loyalty_ability(game, player, pw, 2)
    finally:
        player.end_intent("split")
    resolve_stack(game)


class TestChandraFlameshaperProperties:
    """Static card data should match the FDN 81 spec."""

    def test_is_planeswalker(self) -> None:
        assert isinstance(ChandraFlameshaper(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert printed_class(ChandraFlameshaper(owner=None)) is ChandraFlameshaper

    def test_mana_cost(self) -> None:
        assert ChandraFlameshaper(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")


class TestChandraFlameshaperMinus4Split:
    """−4: 8 damage divided as the controller chooses — a Player Query."""

    def test_intent_chooses_the_split(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw, (a, b) = _setup_minus4(game, 2)
        _minus4(game, p1, pw, [a, b], numbers=(5,))
        assert a.damage_marked == 5
        assert b.damage_marked == 3

    def test_baseline_takes_first_offered_lowest(self) -> None:
        # NUMBER options are offered ascending, so a preference-free answer
        # assigns 1 to each queried target and the remainder to the last.
        game = create_game()
        p1 = game.players[0]
        pw, targets = _setup_minus4(game, 3)
        _minus4(game, p1, pw, targets)
        assert [t.damage_marked for t in targets] == [1, 1, 6]

    def test_each_queried_target_must_get_at_least_one(self) -> None:
        # First of three targets: 8 left, two targets after it → options 1..6.
        game = create_game()
        p1 = game.players[0]
        pw, targets = _setup_minus4(game, 3)
        _minus4(game, p1, pw, targets)
        number_queries = p1.transcript.queries(DecisionKind.NUMBER)
        assert len(number_queries) == 2  # the last target is forced, no query
        first_values = [dict(o.attrs)["value"] for o in number_queries[0].options]
        assert first_values == [1, 2, 3, 4, 5, 6]

    def test_single_target_takes_all_8_without_a_query(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw, (only,) = _setup_minus4(game, 1)
        _minus4(game, p1, pw, [only])
        assert only.damage_marked == 8
        assert p1.transcript.queries(DecisionKind.NUMBER) == []
