"""Every selected HOB oracle must pass its authoritative behavioral suite."""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/hob-medium"
ORACLE = BENCH / "data/test_oracle_workspace"
CARDS = ("hob_12", "hob_36", "hob_70", "hob_131", "hob_169")


@pytest.mark.parametrize("card_id", CARDS)
def test_selected_oracle_passes_audited_suite(card_id, tmp_path):
    impl = ORACLE / "cards/hob" / card_id / "card_impl.py"
    suite = BENCH / "data/tests/audited/hob" / card_id / "tests.py"
    assert impl.is_file(), f"Missing oracle: {impl}"
    assert suite.is_file(), f"Missing audited suite: {suite}"
    classes = [node for node in ast.parse(impl.read_text()).body if isinstance(node, ast.ClassDef)]
    assert any(
        isinstance(member, ast.FunctionDef) and not member.name.startswith("__")
        for cls in classes
        for member in cls.body
    ), f"Stub oracle: {impl}"
    assert any(
        isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        for node in ast.parse(suite.read_text()).body
    ), f"Empty suite: {suite}"
    assert suite.read_bytes() == (ORACLE / "tests/audited/hob" / card_id / "tests.py").read_bytes()
    shutil.copy2(impl, tmp_path / "card_impl.py")
    shutil.copy2(suite, tmp_path / "tests.py")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(tmp_path), str(ORACLE))))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp_path / "tests.py"),
            "-q",
            "--tb=short",
            "--confcutdir",
            str(tmp_path),
            "-c",
            str(ORACLE / "pytest.ini"),
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_authoritative_fdn_regression_passes_v2_baseline():
    suites = BENCH / "data/tests/audited/fdn"
    assert len(list(suites.glob("*/tests.py"))) >= 86
    env = dict(os.environ, PYTHONPATH=str(BENCH / "workspace"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(suites),
            "-q",
            "--tb=short",
            "--confcutdir",
            str(suites.parent),
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
