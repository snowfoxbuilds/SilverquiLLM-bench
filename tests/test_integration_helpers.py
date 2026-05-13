"""Tests for benchmark integration test helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.config import BenchmarkConfig
from silverquillm.card_spec import card_name_to_class_name
from tests.benchmark.test_helpers import (
    create_test_config,
    mock_opencode_blind,
    mock_opencode_test_informed,
)


SAMPLE_SPEC = {
    "name": "Strixhaven Prodigy",
    "type_line": "Creature — Human Wizard",
}

SAMPLE_SPEC_APOSTROPHE = {
    "name": "Ral's Reinforcements",
    "type_line": "Sorcery",
}


class TestMockOpenCodeBlind:
    """Tests for mock_opencode_blind helper."""

    def test_is_callable(self):
        """mock_opencode_blind returns a callable."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC)
        assert callable(mock_fn)

    def test_creates_blind_impl_file(self, tmp_path: Path):
        """Calling the mock creates workspace/blind_impl.py."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("some prompt", workspace)
        assert (workspace / "blind_impl.py").exists()

    def test_blind_impl_compiles(self, tmp_path: Path):
        """The generated blind_impl.py compiles without SyntaxError."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("some prompt", workspace)
        source = (workspace / "blind_impl.py").read_text()
        compile(source, "blind_impl.py", "exec")

    def test_class_name_matches_spec(self, tmp_path: Path):
        """Generated class name matches card_name_to_class_name(spec['name'])."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("some prompt", workspace)
        source = (workspace / "blind_impl.py").read_text()
        expected_class = card_name_to_class_name(SAMPLE_SPEC["name"])
        assert f"class {expected_class}" in source

    def test_class_name_with_apostrophe(self, tmp_path: Path):
        """Works with names containing apostrophes."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC_APOSTROPHE)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        source = (workspace / "blind_impl.py").read_text()
        expected_class = card_name_to_class_name(SAMPLE_SPEC_APOSTROPHE["name"])
        assert f"class {expected_class}" in source
        compile(source, "blind_impl.py", "exec")

    def test_returns_string(self, tmp_path: Path):
        """The mock function returns a string (fake stdout)."""
        mock_fn = mock_opencode_blind(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        result = mock_fn("prompt", workspace)
        assert isinstance(result, str)
        assert len(result) > 0


class TestMockOpenCodeTestInformed:
    """Tests for mock_opencode_test_informed helper."""

    def test_is_callable(self):
        """mock_opencode_test_informed returns a callable."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        assert callable(mock_fn)

    def test_creates_tested_impl(self, tmp_path: Path):
        """Calling the mock creates workspace/tested_impl.py."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        assert (workspace / "tested_impl.py").exists()

    def test_creates_tests_py(self, tmp_path: Path):
        """Calling the mock creates workspace/tests.py."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        assert (workspace / "tests.py").exists()

    def test_tested_impl_compiles(self, tmp_path: Path):
        """The generated tested_impl.py compiles without SyntaxError."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        source = (workspace / "tested_impl.py").read_text()
        compile(source, "tested_impl.py", "exec")

    def test_tests_py_compiles(self, tmp_path: Path):
        """The generated tests.py compiles without SyntaxError."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        source = (workspace / "tests.py").read_text()
        compile(source, "tests.py", "exec")

    def test_tests_py_imports_correct_class(self, tmp_path: Path):
        """tests.py contains import of the correct class name."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mock_fn("prompt", workspace)
        source = (workspace / "tests.py").read_text()
        expected_class = card_name_to_class_name(SAMPLE_SPEC["name"])
        assert expected_class in source
        # Verify it's actually imported
        assert f"import {expected_class}" in source

    def test_returns_string(self, tmp_path: Path):
        """The mock function returns a string (fake stdout)."""
        mock_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        result = mock_fn("prompt", workspace)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_copies_blind_impl_if_exists(self, tmp_path: Path):
        """If blind_impl.py exists, tested_impl.py is a copy of it."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # First run blind mock to create blind_impl.py
        blind_fn = mock_opencode_blind(SAMPLE_SPEC)
        blind_fn("prompt", workspace)
        blind_content = (workspace / "blind_impl.py").read_text()
        # Now run test-informed mock
        test_fn = mock_opencode_test_informed(SAMPLE_SPEC)
        test_fn("prompt", workspace)
        tested_content = (workspace / "tested_impl.py").read_text()
        assert tested_content == blind_content


class TestCreateTestConfig:
    """Tests for create_test_config helper."""

    def test_returns_benchmark_config(self, tmp_path: Path):
        """create_test_config returns a BenchmarkConfig instance."""
        config = create_test_config(tmp_path)
        assert isinstance(config, BenchmarkConfig)

    def test_default_set_code(self, tmp_path: Path):
        """Default set_code is 'sos'."""
        config = create_test_config(tmp_path)
        assert config.set_code == "sos"

    def test_custom_set_code(self, tmp_path: Path):
        """Can override set_code."""
        config = create_test_config(tmp_path, set_code="neo")
        assert config.set_code == "neo"

    def test_output_dir_exists(self, tmp_path: Path):
        """The output_dir path is created on disk."""
        config = create_test_config(tmp_path)
        assert Path(config.output_dir).exists()

    def test_has_required_attributes(self, tmp_path: Path):
        """Config has all expected attributes for a benchmark run."""
        config = create_test_config(tmp_path)
        assert config.name
        assert config.model_name
        assert config.model_provider
        assert config.max_context > 0
        assert config.agent.timeout_per_card > 0
