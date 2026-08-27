"""Phase 2 protocol tests for the non-targeting converted call sites:
ordering query (combat damage order), discard query (cleanup), and the
legend-rule OBJECT query.
"""

from __future__ import annotations

from engine.card import CardImpl, Creature
from engine.decisions import DecisionKind
from engine.game_state import GameState
from engine.player import Player
from engine.queries import Answer
from engine.types import CardType, ManaCost, Supertype, Zone


class FnPlayer(Player):
    """Answers via an optional callback; defaults to the first ``min`` options."""

    def __init__(self, name: str, fn=None):
        super().__init__(name)
        self.fn = fn
        self.transcript: list = []

    def answer(self, query) -> Answer:
        self.transcript.append(query)
        if self.fn is not None:
            result = self.fn(query)
            if result is not None:
                return result
        return Answer(selected=tuple(query.options[: query.min]))


def _creature(name, *, legendary=False):
    supertypes = {Supertype.LEGENDARY} if legendary else set()
    return Creature(name=name, mana_cost=ManaCost(generic=1),
                    base_power=2, base_toughness=2, supertypes=supertypes)


def _put(game, player, zone, card):
    card.owner = player
    card.controller = player
    player.zones[zone].add(card)


class TestOrderingQuery:
    def test_damage_order_query_applies_answer_order(self):
        from engine.combat import declare_attackers_step, declare_blockers_step

        # p0 (attacker controller) reverses any ordering query it receives.
        def reverse_orderings(query):
            if query.min == query.max == len(query.options) and len(query.options) > 1:
                return Answer(selected=tuple(reversed(query.options)))
            return None

        p0 = FnPlayer("P0", fn=reverse_orderings)
        p1 = FnPlayer("P1")
        game = GameState([p0, p1])

        attacker = _creature("Attacker")
        attacker.summoning_sick = False
        b1 = _creature("Blocker1")
        b2 = _creature("Blocker2")
        _put(game, p0, Zone.BATTLEFIELD, attacker)
        _put(game, p1, Zone.BATTLEFIELD, b1)
        _put(game, p1, Zone.BATTLEFIELD, b2)

        declare_attackers_step(game, [attacker])
        declare_blockers_step(game, {b1: attacker, b2: attacker})

        # An ordering query (min == max == len) was raised to the attacker's
        # controller, and the Answer's order is the damage-assignment order.
        ordering_queries = [
            q for q in p0.transcript if q.min == q.max == len(q.options) > 1
        ]
        assert len(ordering_queries) == 1
        assert game.combat_state.attacker_blockers[attacker] == [b2, b1]


class TestDiscardQuery:
    def test_cleanup_discard_raises_object_queries_until_hand_size(self):
        from engine.turn import _do_cleanup_step

        p0 = FnPlayer("P0")
        p1 = FnPlayer("P1")
        game = GameState([p0, p1])
        for i in range(9):
            _put(game, p0, Zone.HAND, CardImpl(name=f"C{i}", card_types={CardType.INSTANT}))

        _do_cleanup_step(game)

        assert len(p0.zones[Zone.HAND]) == 7
        discard_queries = [
            q for q in p0.transcript
            if q.options and all(o.kind is DecisionKind.OBJECT for o in q.options)
        ]
        assert len(discard_queries) == 2  # 9 -> 7


class TestLegendRuleQuery:
    def test_legend_rule_keeps_chosen_object(self):
        from engine.state_based_actions import resolve_state_based_actions

        p0 = FnPlayer("P0")
        p1 = FnPlayer("P1")
        game = GameState([p0, p1])
        a = _creature("Hero", legendary=True)
        b = _creature("Hero", legendary=True)
        _put(game, p0, Zone.BATTLEFIELD, a)
        _put(game, p0, Zone.BATTLEFIELD, b)

        resolve_state_based_actions(game)

        bf = list(p0.zones[Zone.BATTLEFIELD].get_all())
        gy = list(p0.zones[Zone.GRAVEYARD].get_all())
        assert len(bf) == 1
        assert len(gy) == 1
        assert {id(x) for x in bf + gy} == {id(a), id(b)}
