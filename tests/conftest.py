"""Pytest configuration for the test suite."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(items):
    """Filter out imported functions whose definition lives in silverquillm/ (not tests/silverquillm/)."""
    items[:] = [
        item
        for item in items
        if not _is_from_benchmark_package(item)
    ]


def _is_from_benchmark_package(item) -> bool:
    """Return True if the item's source is the silverquillm/ package (not tests/silverquillm/)."""
    fspath = getattr(item, "fspath", None)
    if fspath is not None:
        strpath = fspath.strpath if hasattr(fspath, "strpath") else str(fspath)
        # Only filter out if it's the top-level silverquillm/ dir, not tests/silverquillm/
        parts = strpath.replace("\\", "/").split("/")
        # If "silverquillm" appears but NOT after "tests", filter it
        if "silverquillm" in parts:
            idx = parts.index("silverquillm")
            if idx == 0 or parts[idx - 1] != "tests":
                return True
    # Also filter if the object's module starts with "silverquillm."
    if hasattr(item, "obj"):
        module = getattr(item.obj, "__module__", "")
        if module.startswith("silverquillm.") and not module.startswith("tests.silverquillm."):
            return True
    return False
