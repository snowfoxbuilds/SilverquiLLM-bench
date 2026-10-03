"""Reference test for FDN 81 — Chandra, Flameshaper.

Illustrative test covering the **−4 "divided as you choose" damage split**:
the split is a player choice re-expressed as NUMBER Player Queries (one per
target except the last, which takes the forced remainder), never a hardcoded
distribution. A baseline answer takes the first-offered (lowest) number; a
card intent picks the split via a ``Decision.number`` preference.
"""

from __future__ import annotations

from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
from engine.card import Creature, Planeswalker
from engine.decisions import Decision, DecisionKind, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, Zone
from test_utils import create_game


def _setup_minus4(game, n_targets):
    """Chandra on p1's battlefield with ``n_targets`` chosen creature targets."""
    p1, p2 = game.players[0], game.players[1]
    pw = ChandraFlameshaper(owner=p1, controller=p1)
    p1.zones[Zone.BATTLEFIELD].add(pw)
    targets = []
    for i in range(n_targets):
        c = Creature(name=f"Target{i}", base_power=4, base_toughness=9,
                     owner=p2, controller=p2)
        p2.zones[Zone.BATTLEFIELD].add(c)
        targets.append(c)
    pw.chosen_targets = targets
    minus4 = next(a for a in pw.get_loyalty_abilities() if a.loyalty_cost == -4)
    return pw, targets, minus4


class TestChandraFlameshaperProperties:
    """Static card data should match the FDN 81 spec."""

    def test_is_planeswalker(self) -> None:
        assert isinstance(ChandraFlameshaper(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert ChandraFlameshaper(owner=None).name == "Chandra, Flameshaper"

    def test_mana_cost(self) -> None:
        assert ChandraFlameshaper(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")


class TestChandraFlameshaperMinus4Split:
    """−4: 8 damage divided as the controller chooses — a Player Query."""

    def test_intent_chooses_the_split(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw, (a, b), minus4 = _setup_minus4(game, 2)
        p1.start_intent("split", Intent(
            pattern=GameRef(card=frozenset({("name", "Chandra, Flameshaper")})),
            preferences=(Decision.number(5),),
        ))
        minus4.effect(game)
        p1.end_intent("split")
        assert a.damage_marked == 5
        assert b.damage_marked == 3

    def test_baseline_takes_first_offered_lowest(self) -> None:
        # NUMBER options are offered ascending, so a preference-free baseline
        # assigns 1 to each queried target and the remainder to the last.
        game = create_game()
        p1 = game.players[0]
        pw, targets, minus4 = _setup_minus4(game, 3)
        p1.set_baseline(Intent(pattern=GameRef(), preferences=()))
        minus4.effect(game)
        assert [t.damage_marked for t in targets] == [1, 1, 6]

    def test_each_queried_target_must_get_at_least_one(self) -> None:
        # First of three targets: 8 left, two targets after it → options 1..6.
        game = create_game()
        p1 = game.players[0]
        pw, targets, minus4 = _setup_minus4(game, 3)
        p1.set_baseline(Intent(pattern=GameRef(), preferences=()))
        minus4.effect(game)
        number_queries = p1.transcript.queries(DecisionKind.NUMBER)
        assert len(number_queries) == 2  # the last target is forced, no query
        first_values = [dict(o.attrs)["value"] for o in number_queries[0].options]
        assert first_values == [1, 2, 3, 4, 5, 6]

    def test_single_target_takes_all_8_without_a_query(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw, (only,), minus4 = _setup_minus4(game, 1)
        p1.set_baseline(Intent(pattern=GameRef(), preferences=()))
        minus4.effect(game)
        assert only.damage_marked == 8
        assert p1.transcript.queries(DecisionKind.NUMBER) == []
