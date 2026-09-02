"""Tests for the V2 Player Query additions to the replay layer:
benchmark-parameterized engine selection and the QUERY_UNANSWERED /
PROTOCOL_ERROR divergence classification.
"""

from __future__ import annotations

import pytest

from silverquillm.replay.cli import _resolve_workspace
from silverquillm.replay.validation import DivergenceType, classify_step_exception


class TestNewDivergenceTypes:
    def test_query_unanswered_and_protocol_error_exist(self):
        assert DivergenceType.QUERY_UNANSWERED.value == "QUERY_UNANSWERED"
        assert DivergenceType.PROTOCOL_ERROR.value == "PROTOCOL_ERROR"


class TestClassifyStepException:
    # Classification matches module-qualified names in the MRO, so the fakes
    # carry the V2 engine module — no import of V2-only classes needed here.
    def test_protocol_error_family_maps_to_protocol_error(self):
        class ProtocolError(Exception):
            __module__ = "engine.decisions"

        class MalformedAttrsError(ProtocolError):
            pass

        assert classify_step_exception(ProtocolError()) is DivergenceType.PROTOCOL_ERROR
        assert (
            classify_step_exception(MalformedAttrsError())
            is DivergenceType.PROTOCOL_ERROR
        )

    def test_unmatched_query_maps_to_query_unanswered(self):
        class IntentError(Exception):
            pass

        class UnmatchedQueryError(IntentError):
            __module__ = "engine.decisions"

        assert (
            classify_step_exception(UnmatchedQueryError())
            is DivergenceType.QUERY_UNANSWERED
        )

    def test_same_named_foreign_class_is_not_a_protocol_error(self):
        # A third-party exception that merely shares the name must classify
        # as ENGINE_ERROR — only engine.decisions.ProtocolError qualifies.
        class ProtocolError(Exception):
            pass  # __module__ is this test module, not engine.decisions

        assert classify_step_exception(ProtocolError()) is DivergenceType.ENGINE_ERROR

    def test_other_exceptions_map_to_engine_error(self):
        assert classify_step_exception(ValueError("x")) is DivergenceType.ENGINE_ERROR
        assert classify_step_exception(KeyError("y")) is DivergenceType.ENGINE_ERROR


class TestBenchmarkEngineSelection:
    def test_unknown_benchmark_raises(self):
        import click

        with pytest.raises(click.ClickException):
            _resolve_workspace("does_not_exist", None)

    def test_hob_medium_benchmark_resolves_workspace(self):
        ws = _resolve_workspace("hob-medium", None)
        assert ws is not None
        assert str(ws).endswith("benchmarks/hob-medium/workspace")
