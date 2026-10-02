"""Select the local oracle for direct runs of each portable grader suite."""

import importlib
import sys


def pytest_pycollect_makemodule(module_path, parent):
    if module_path.name == 'tests.py' and module_path.parent.name.startswith('hob_'):
        sys.modules['card_impl'] = importlib.import_module(
            f'cards.hob.{module_path.parent.name}.card_impl'
        )
