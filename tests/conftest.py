"""Pytest configuration for the test suite."""


def pytest_collection_modifyitems(items):
    """Filter out imported functions whose definition lives in benchmark/."""
    items[:] = [
        item
        for item in items
        if "benchmark" not in getattr(item, "fspath", "").strpath
        if not (
            hasattr(item, "obj")
            and getattr(item.obj, "__module__", "").startswith("benchmark.")
        )
    ]
