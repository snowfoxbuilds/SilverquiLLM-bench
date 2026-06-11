"""Unit tests for the intent-based DeterministicPlayer (engine/intent_player.py).

Routing (pattern → source refs), preference-based answering, the Baseline
Intent slot, ambiguity / unmatched hard errors, decline semantics, ordering
queries, postconditions, and the query transcript.
"""

from __future__ import annotations

import pytest

from engine.decisions import (
    AmbiguousIntentError,
    Decision,
    DecisionKind,
    GameRef,
    PostconditionError,
    UnmatchedQueryError,
)
from engine.intent_player import DeterministicPlayer, Intent
from engine.queries import PlayerQuery


def _card_source(name: str):
    return Decision.obj(ref=GameRef(card=frozenset({("name", name)})))


def _obj_option(instance: int, **attrs):
    return Decision.obj(ref=GameRef(object=frozenset({("instance", instance)})),
                        instance=instance, **attrs)


def _query(source_name, options, *, min=1, max=1):
    return PlayerQuery(
        source=(_card_source(source_name),),
        prompt="?",
        options=tuple(options),
        min=min,
        max=max,
    )


class TestRouting:
    def test_card_intent_routes_and_preference_selects(self):
        p = DeterministicPlayer("P0")
        p.start_intent("strike", Intent(
            pattern=GameRef(card=frozenset({("name", "Bushwhack")})),
            preferences=(Decision.obj(color="R"),),
        ))
        red = _obj_option(1, color="R")
        green = _obj_option(2, color="G")
        ans = p.answer(_query("Bushwhack", [green, red]))
        assert ans.selected == (red,)

    def test_unmatched_query_with_no_baseline_raises(self):
        p = DeterministicPlayer("P0")
        p.start_intent("strike", Intent(
            pattern=GameRef(card=frozenset({("name", "Bushwhack")})),
            preferences=(Decision.yes(),),
        ))
        with pytest.raises(UnmatchedQueryError):
            p.answer(_query("OtherCard", [Decision.yes(), Decision.no()]))

    def test_two_matching_intents_is_ambiguous(self):
        p = DeterministicPlayer("P0")
        pattern = GameRef(card=frozenset({("name", "Bushwhack")}))
        p.start_intent("a", Intent(pattern=pattern, preferences=(Decision.yes(),)))
        p.start_intent("b", Intent(pattern=pattern, preferences=(Decision.no(),)))
        with pytest.raises(AmbiguousIntentError):
            p.answer(_query("Bushwhack", [Decision.yes(), Decision.no()]))


class TestBaseline:
    def test_baseline_used_when_no_card_intent_matches(self):
        p = DeterministicPlayer("P0")
        p.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.no(),)))
        ans = p.answer(_query("AnyCard", [Decision.yes(), Decision.no()]))
        assert ans.selected == (Decision.no(),)

    def test_card_intent_takes_precedence_over_baseline(self):
        p = DeterministicPlayer("P0")
        p.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.no(),)))
        p.start_intent("yes", Intent(
            pattern=GameRef(card=frozenset({("name", "Bushwhack")})),
            preferences=(Decision.yes(),),
        ))
        ans = p.answer(_query("Bushwhack", [Decision.yes(), Decision.no()]))
        assert ans.selected == (Decision.yes(),)


class TestDeclineAndOrdering:
    def test_decline_when_min_zero_and_no_preference_matches(self):
        p = DeterministicPlayer("P0")
        p.set_baseline(Intent(pattern=GameRef(), preferences=()))
        q = _query("AnyCard", [_obj_option(1, color="R")], min=0, max=1)
        ans = p.answer(q)
        assert ans.selected == ()

    def test_ordering_query_uses_preference_order_then_fills(self):
        p = DeterministicPlayer("P0")
        a = _obj_option(1, color="R")
        b = _obj_option(2, color="G")
        c = _obj_option(3, color="W")
        p.set_baseline(Intent(
            pattern=GameRef(),
            preferences=(Decision.obj(color="W"), Decision.obj(color="G")),
        ))
        # ordering query: min == max == len; preferences W,G come first, R fills.
        q = _query("AnyCard", [a, b, c], min=3, max=3)
        ans = p.answer(q)
        assert ans.selected == (c, b, a)


class TestPostcondition:
    def test_passing_postcondition_is_ok(self):
        p = DeterministicPlayer("P0")
        p.start_intent("x", Intent(
            pattern=GameRef(card=frozenset({("name", "C")})),
            preferences=(Decision.yes(),),
            postcondition=lambda g: True,
        ))
        p.end_intent("x", game=object())

    def test_failing_postcondition_raises(self):
        p = DeterministicPlayer("P0")
        p.start_intent("x", Intent(
            pattern=GameRef(card=frozenset({("name", "C")})),
            preferences=(Decision.yes(),),
            postcondition=lambda g: False,
        ))
        with pytest.raises(PostconditionError):
            p.end_intent("x", game=object())


class TestTranscript:
    def test_transcript_logs_queries_filterable_by_kind(self):
        p = DeterministicPlayer("P0")
        p.set_baseline(Intent(pattern=GameRef(), preferences=()))
        p.answer(_query("C", [Decision.yes(), Decision.no()]))  # BOOL
        p.answer(_query("C", [_obj_option(1, color="R")]))       # OBJECT
        object_queries = p.transcript.queries(kind=DecisionKind.OBJECT)
        assert len(object_queries) == 1
        assert any(("color", "R") in opt.attrs for opt in object_queries[-1].options)
