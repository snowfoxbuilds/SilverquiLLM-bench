"""Unit tests for the Player Query layer (engine/queries.py).

PlayerQuery, Answer, and boundary validation. Boundary failures are engine-fault
(ProtocolError family); answer failures are test-fault (InvalidAnswerError).
"""

from __future__ import annotations

import pytest

from engine.decisions import (
    Decision,
    DecisionKind,
    InvalidAnswerError,
    InvalidOptionsError,
    MalformedAttrsError,
    PlayerDecision,
    UnknownKindError,
)
from engine.queries import Answer, PlayerQuery, validate_answer, validate_query


def _bool_query(min_=1, max_=1):
    return PlayerQuery(
        source=(Decision.obj(name="Strike"),),
        prompt="yes or no?",
        options=(Decision.yes(), Decision.no()),
        min=min_,
        max=max_,
    )


class TestQueryConstruction:
    def test_query_and_answer_are_frozen(self):
        q = _bool_query()
        with pytest.raises(Exception):
            q.min = 5  # type: ignore[misc]
        a = Answer(selected=(Decision.yes(),))
        with pytest.raises(Exception):
            a.selected = ()  # type: ignore[misc]


class TestBoundaryValidation:
    def test_well_formed_query_passes(self):
        validate_query(_bool_query())

    def test_empty_options_with_min_gt_zero_is_invalid(self):
        q = PlayerQuery(source=(), prompt="?", options=(), min=1, max=1)
        with pytest.raises(InvalidOptionsError):
            validate_query(q)

    def test_empty_options_with_min_zero_is_allowed(self):
        q = PlayerQuery(source=(), prompt="?", options=(), min=0, max=0)
        validate_query(q)

    def test_duplicate_options_are_invalid(self):
        q = PlayerQuery(
            source=(),
            prompt="?",
            options=(Decision.yes(), Decision.yes()),
            min=1,
            max=1,
        )
        with pytest.raises(InvalidOptionsError):
            validate_query(q)

    def test_max_exceeding_option_count_is_invalid(self):
        q = PlayerQuery(
            source=(),
            prompt="?",
            options=(Decision.yes(),),
            min=1,
            max=2,
        )
        with pytest.raises(InvalidOptionsError):
            validate_query(q)

    def test_max_less_than_min_is_invalid(self):
        q = PlayerQuery(
            source=(),
            prompt="?",
            options=(Decision.yes(), Decision.no()),
            min=2,
            max=1,
        )
        with pytest.raises(InvalidOptionsError):
            validate_query(q)

    def test_unknown_kind_option_raises_unknown_kind(self):
        bad = PlayerDecision(kind="not_a_kind", attrs=frozenset())  # type: ignore[arg-type]
        q = PlayerQuery(source=(), prompt="?", options=(bad,), min=1, max=1)
        with pytest.raises(UnknownKindError):
            validate_query(q)

    def test_malformed_attrs_option_raises_malformed_attrs(self):
        bad = PlayerDecision(
            kind=DecisionKind.MANA, attrs=frozenset({("color", "purple")})
        )
        q = PlayerQuery(source=(), prompt="?", options=(bad,), min=1, max=1)
        with pytest.raises(MalformedAttrsError):
            validate_query(q)

    def test_engine_surplus_attr_on_option_is_tolerated(self):
        # Engines may attach extra attrs to an option (Extension policy:
        # attrs surplus-tolerant). The boundary check must not reject the
        # query just because of an unknown-but-hashable engine-private key.
        with_surplus = PlayerDecision(
            kind=DecisionKind.MANA,
            attrs=frozenset({("color", "R"), ("engine_private_fact", 1)}),
        )
        q = PlayerQuery(source=(), prompt="?", options=(with_surplus,), min=1, max=1)
        validate_query(q)


class TestAnswerValidation:
    def test_valid_answer_passes(self):
        q = _bool_query()
        validate_answer(q, Answer(selected=(Decision.yes(),)))

    def test_too_few_selected_is_invalid(self):
        q = _bool_query(min_=1, max_=1)
        with pytest.raises(InvalidAnswerError):
            validate_answer(q, Answer(selected=()))

    def test_too_many_selected_is_invalid(self):
        q = _bool_query(min_=1, max_=1)
        with pytest.raises(InvalidAnswerError):
            validate_answer(q, Answer(selected=(Decision.yes(), Decision.no())))

    def test_selection_not_among_options_is_invalid(self):
        q = _bool_query()
        with pytest.raises(InvalidAnswerError):
            validate_answer(q, Answer(selected=(Decision.number(3),)))

    def test_duplicate_selection_is_invalid(self):
        q = PlayerQuery(
            source=(),
            prompt="?",
            options=(Decision.yes(), Decision.no()),
            min=1,
            max=2,
        )
        with pytest.raises(InvalidAnswerError):
            validate_answer(q, Answer(selected=(Decision.yes(), Decision.yes())))

    def test_decline_is_legal_iff_min_zero(self):
        decline = Answer(selected=())
        validate_answer(_bool_query(min_=0, max_=1), decline)  # legal
        with pytest.raises(InvalidAnswerError):
            validate_answer(_bool_query(min_=1, max_=1), decline)
