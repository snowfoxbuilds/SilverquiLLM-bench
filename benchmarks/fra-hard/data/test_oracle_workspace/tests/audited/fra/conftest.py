"""Select the local oracle for direct runs of each portable grader suite."""

import importlib
import sys


def pytest_pycollect_makemodule(module_path, parent):
    if module_path.name == "tests.py" and module_path.parent.name.startswith("fra_"):
        sys.modules["card_impl"] = importlib.import_module(
            f"cards.fra.{module_path.parent.name}.card_impl"
        )
