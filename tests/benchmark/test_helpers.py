"""Reusable test helpers for benchmark integration tests.

Provides mock OpenCode callables and config factories so that integration
tests can exercise the real pipeline while mocking only the subprocess.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import Callable

from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.template_gen import card_name_to_class_name, _determine_base_class


def mock_opencode_blind(card_spec: dict) -> Callable[[str, Path], str]:
    """Return a mock ``_run_agent`` that writes a minimal blind implementation.

    The returned callable matches the signature ``(prompt: str, workspace: Path) -> str``.
    It writes a minimal valid Python class to ``workspace/blind_impl.py`` using the
    card's class name and correct base class derived from the spec's type_line.

    Parameters
    ----------
    card_spec:
        Card specification dict (must contain at least ``name`` and ``type_line``).

    Returns
    -------
    Callable[[str, Path], str]
        A function that simulates a successful OpenCode blind-phase run.
    """
    class_name = card_name_to_class_name(card_spec["name"])
    base_class, _card_types = _determine_base_class(card_spec.get("type_line", ""))

    def _mock(prompt: str, workspace: Path) -> str:
        impl_source = textwrap.dedent(f"""\
            from engine.card import *
            from engine.types import *


            class {class_name}({base_class}):
                \"\"\"{card_spec["name"]}.\"\"\"\n
                def __init__(self, **kwargs):
                    super().__init__(
                        name="{card_spec["name"]}",
                        **kwargs,
                    )
        """)
        (workspace / "blind_impl.py").write_text(impl_source)
        return (
            f"OpenCode session completed.\n"
            f"Tokens used: 1234 | Context: 5000/200000\n"
            f"Generated {class_name} implementation."
        )

    return _mock


def mock_opencode_test_informed(card_spec: dict) -> Callable[[str, Path], str]:
    """Return a mock ``_run_agent`` that writes a test-informed implementation.

    The returned callable:
    - Copies ``workspace/blind_impl.py`` to ``workspace/tested_impl.py``
      (or writes a slightly modified version if blind_impl.py doesn't exist).
    - Writes a minimal ``workspace/tests.py`` with 2-3 basic test cases that
      import the class and verify it exists with the correct ``name`` attribute.

    Parameters
    ----------
    card_spec:
        Card specification dict (must contain at least ``name`` and ``type_line``).

    Returns
    -------
    Callable[[str, Path], str]
        A function that simulates a successful OpenCode test-informed run.
    """
    class_name = card_name_to_class_name(card_spec["name"])
    base_class, _card_types = _determine_base_class(card_spec.get("type_line", ""))

    def _mock(prompt: str, workspace: Path) -> str:
        # Copy or create tested_impl.py
        blind_path = workspace / "blind_impl.py"
        tested_path = workspace / "tested_impl.py"
        if blind_path.exists():
            shutil.copy2(blind_path, tested_path)
        else:
            impl_source = textwrap.dedent(f"""\
                from engine.card import *
                from engine.types import *


                class {class_name}({base_class}):
                    \"\"\"{card_spec["name"]}.\"\"\"\n
                    def __init__(self, **kwargs):
                        super().__init__(
                            name="{card_spec["name"]}",
                            **kwargs,
                        )
            """)
            tested_path.write_text(impl_source)

        # Ensure card_impl.py exists (tests.py imports from card_impl)
        card_impl_path = workspace / "card_impl.py"
        if not card_impl_path.exists():
            shutil.copy2(tested_path, card_impl_path)

        # Write tests.py
        tests_source = textwrap.dedent(f"""\
            from card_impl import {class_name}


            def test_class_exists():
                \"\"\"Verify the class can be instantiated.\"\"\"
                obj = {class_name}()
                assert obj is not None


            def test_name_attribute():
                \"\"\"Verify the card has the correct name.\"\"\"
                obj = {class_name}()
                assert obj.name == "{card_spec["name"]}"


            def test_is_instance():
                \"\"\"Verify correct base class inheritance.\"\"\"
                obj = {class_name}()
                assert type(obj).__name__ == "{class_name}"
        """)
        (workspace / "tests.py").write_text(tests_source)

        return (
            f"OpenCode session completed.\n"
            f"Tokens used: 2345 | Context: 8000/200000\n"
            f"Generated tests and refined {class_name} implementation."
        )

    return _mock


def create_test_config(tmp_path: Path, set_code: str = "sos") -> BenchmarkConfig:
    """Create a BenchmarkConfig suitable for integration tests.

    Uses temp paths and conservative settings (low timeout, single test round).

    Parameters
    ----------
    tmp_path:
        Pytest ``tmp_path`` fixture or any temporary directory.
    set_code:
        Card set code to use. Defaults to ``"sos"``.

    Returns
    -------
    BenchmarkConfig
        A fully-populated config dataclass for testing.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    specs_dir = tmp_path / "card_specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    return BenchmarkConfig(
        name="test-run",
        set_code=set_code,
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            adapter="opencode",
            max_test_rounds=1,
            timeout_per_card=10,
            disable_web_search=True,
        ),
        card_specs_dir=str(specs_dir),
        engine_docs_path=str(tmp_path / "engine_docs"),
        template_dir=str(tmp_path / "templates"),
        output_dir=str(output_dir),
    )
