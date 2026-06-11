"""Tests for the MSH Player Query additions to the replay layer:
benchmark-parameterized engine selection and the QUERY_UNANSWERED /
PROTOCOL_ERROR divergence classification.
"""

from __future__ import annotations

import sys

import pytest

from silverquillm.replay.cli import _select_benchmark_engine
from silverquillm.replay.validation import DivergenceType, classify_step_exception


class TestNewDivergenceTypes:
    def test_query_unanswered_and_protocol_error_exist(self):
        assert DivergenceType.QUERY_UNANSWERED.value == "QUERY_UNANSWERED"
        assert DivergenceType.PROTOCOL_ERROR.value == "PROTOCOL_ERROR"


class TestClassifyStepException:
    def test_protocol_error_family_maps_to_protocol_error(self):
        class ProtocolError(Exception):
            pass

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
            pass

        assert (
            classify_step_exception(UnmatchedQueryError())
            is DivergenceType.QUERY_UNANSWERED
        )

    def test_other_exceptions_map_to_engine_error(self):
        assert classify_step_exception(ValueError("x")) is DivergenceType.ENGINE_ERROR
        assert classify_step_exception(KeyError("y")) is DivergenceType.ENGINE_ERROR


class TestBenchmarkEngineSelection:
    def test_unknown_benchmark_raises(self):
        import click

        with pytest.raises(click.ClickException):
            _select_benchmark_engine("does_not_exist")

    def test_msh_benchmark_adds_workspace_to_path(self):
        saved = list(sys.path)
        try:
            _select_benchmark_engine("msh")
            assert any(
                p.endswith("benchmarks/msh/workspace") for p in sys.path
            )
        finally:
            sys.path[:] = saved
