"""Tests for the per-card audited test directory structure and conftest.py infrastructure.

Validates TODO item 5 requirements:
- Directory structure: tests/audited/fdn/ and tests/audited/sos/
- pyproject.toml configured for tests.py discovery and importlib mode
- FDN conftest injects synthetic card_impl backed by CardRegistry
- Collector-directory detection resolves correct card per test directory
- Multi-word card class names are exposed correctly (e.g. AjaniCallerOfThePride)
- SOS conftest fails clearly when stubs are absent
- SOS conftest replaces existing FDN card_impl in sys.modules
- Explicit evaluator-provided card_impl.py is not overridden by conftest
- Sample FDN Plains test can run and import Plains from card_impl
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

# Root of project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_fdn_conftest_module() -> types.ModuleType:
    """Load the FDN conftest without triggering module-level injection.

    Places a fake real-file-backed card_impl in sys.modules so the
    ``if not _has_explicit_card_impl():`` guard at the bottom of the
    conftest skips injection.  Returns the loaded module with all
    helper functions available.
    """
    conftest_path = _PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "conftest.py"
    spec = importlib.util.spec_from_file_location(
        "fdn_conftest_test", conftest_path,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    original = sys.modules.get("card_impl")
    try:
        # Fake explicit card_impl so module-level injection is skipped
        fake_impl = types.ModuleType("card_impl")
        fake_impl.__file__ = str(_PROJECT_ROOT / "pyproject.toml")
        sys.modules["card_impl"] = fake_impl
        spec.loader.exec_module(mod)
    finally:
        if original is not None:
            sys.modules["card_impl"] = original
        else:
            sys.modules.pop("card_impl", None)
    return mod


def _load_sos_conftest_module() -> types.ModuleType:
    """Load the SOS conftest without triggering module-level injection.

    Same trick: fake explicit card_impl to skip module-level guard.
    """
    conftest_path = _PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py"
    spec = importlib.util.spec_from_file_location(
        "sos_conftest_test", conftest_path,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    original = sys.modules.get("card_impl")
    try:
        fake_impl = types.ModuleType("card_impl")
        fake_impl.__file__ = str(_PROJECT_ROOT / "pyproject.toml")
        sys.modules["card_impl"] = fake_impl
        spec.loader.exec_module(mod)
    finally:
        if original is not None:
            sys.modules["card_impl"] = original
        else:
            sys.modules.pop("card_impl", None)
    return mod


class TestDirectoryStructure:
    """Verify required audited test directories and files exist."""

    def test_audited_root_exists(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited").is_dir()

    def test_audited_root_has_init(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "__init__.py").is_file()

    def test_fdn_directory_exists(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn").is_dir()

    def test_fdn_has_init(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "__init__.py").is_file()

    def test_fdn_has_conftest(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "conftest.py").is_file()

    def test_sos_directory_exists(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos").is_dir()

    def test_sos_has_init(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "__init__.py").is_file()

    def test_sos_has_conftest(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py").is_file()

    def test_fdn_272_directory_exists(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272").is_dir()

    def test_fdn_272_has_tests_py(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272" / "tests.py").is_file()

    def test_fdn_272_has_init(self) -> None:
        assert (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272" / "__init__.py").is_file()


class TestPyprojectConfig:
    """Verify pyproject.toml is configured for audited test discovery."""

    def test_python_files_includes_tests_py(self) -> None:
        pyproject = (_PROJECT_ROOT / "pyproject.toml").read_text()
        assert "tests.py" in pyproject

    def test_import_mode_importlib(self) -> None:
        pyproject = (_PROJECT_ROOT / "pyproject.toml").read_text()
        assert "importlib" in pyproject


class TestFDNConftestBehavior:
    """Behavioral tests for FDN conftest card_impl module injection."""

    def test_build_registry_returns_populated_registry(self) -> None:
        """_build_registry() must return a CardRegistry with FDN cards."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        all_cards = registry.list_all()
        assert len(all_cards) > 0
        assert "Plains" in all_cards

    def test_build_collector_maps_includes_collector_numbers(self) -> None:
        """_build_collector_maps() must map collector numbers to (class, name) tuples."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        assert len(cn_to_entry) > 0
        for cn, (cls, name) in cn_to_entry.items():
            assert isinstance(cn, str)
            assert isinstance(cls, type)
            assert isinstance(name, str)
            break

    def test_classname_map_exposes_multiword_card_classes(self) -> None:
        """classname_to_class must map multi-word card class names.

        e.g. 'Ajani, Caller of the Pride' -> AjaniCallerOfThePride class
        """
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        _cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)

        # Check that at least one multi-word class name exists
        multiword_names = [
            n for n in classname_to_class
            if any(c.isupper() for c in n[1:])  # has uppercase after first char
            and len(n) > 10
        ]
        assert len(multiword_names) > 0, (
            "classname_to_class must contain multi-word card class names "
            "like AjaniCallerOfThePride"
        )

    def test_synthetic_module_getattr_resolves_plains(self) -> None:
        """Synthetic card_impl __getattr__ must resolve 'Plains' by class name."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)

        plains_cls = synthetic.__getattr__("Plains")
        assert plains_cls.__name__ == "Plains"

    def test_synthetic_module_getattr_resolves_multiword_class(self) -> None:
        """Synthetic card_impl must resolve multi-word class names like AjaniCallerOfThePride."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)

        # Pick any multi-word class from the registry
        multiword = next(
            (n for n in classname_to_class if len(n) > 10 and any(c.isupper() for c in n[1:])),
            None,
        )
        assert multiword is not None, "Need at least one multi-word card class"
        result = synthetic.__getattr__(multiword)
        assert result.__name__ == multiword

    def test_synthetic_module_raises_attributeerror_for_unknown(self) -> None:
        """card_impl must raise AttributeError for names not in FDN registry."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)

        with pytest.raises(AttributeError, match="card_impl has no attribute"):
            synthetic.__getattr__("NonExistentCard999")

    def test_synthetic_module_has_fdn_file_marker(self) -> None:
        """Synthetic module __file__ must be '<synthetic:fdn_conftest>'."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)
        assert synthetic.__file__ == "<synthetic:fdn_conftest>"


class TestCollectorDirectoryDetection:
    """Test collector-directory detection used by both FDN and SOS conftest."""

    def test_fdn_has_detect_collector_dir_function(self) -> None:
        """FDN conftest must have _detect_collector_dir() callable."""
        fdn = _load_fdn_conftest_module()
        assert callable(getattr(fdn, "_detect_collector_dir", None))

    def test_sos_has_detect_collector_dir_function(self) -> None:
        """SOS conftest must have _detect_collector_dir() callable."""
        sos = _load_sos_conftest_module()
        assert callable(getattr(sos, "_detect_collector_dir", None))

    def test_fdn_getattr_calls_detect_collector_dir(self) -> None:
        """FDN synthetic module __getattr__ must call _detect_collector_dir()."""
        source = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "conftest.py").read_text()
        # _make_card_impl_module's inner _getattr must reference _detect_collector_dir
        assert "_detect_collector_dir()" in source

    def test_sos_getattr_calls_detect_collector_dir(self) -> None:
        """SOS synthetic module __getattr__ must call _detect_collector_dir()."""
        source = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py").read_text()
        assert "_detect_collector_dir()" in source


class TestExplicitCardImplOverrideProtection:
    """Verify conftest does not override an evaluator-provided card_impl.py."""

    def test_has_explicit_detects_real_file_backed_module(self) -> None:
        """_has_explicit_card_impl() returns True when sys.modules has a real-file module."""
        fdn = _load_fdn_conftest_module()
        original = sys.modules.get("card_impl")
        try:
            real_impl = types.ModuleType("card_impl")
            real_impl.__file__ = str(_PROJECT_ROOT / "pyproject.toml")
            sys.modules["card_impl"] = real_impl
            assert fdn._has_explicit_card_impl() is True
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)

    def test_has_explicit_ignores_synthetic_module(self) -> None:
        """_has_explicit_card_impl() returns False for synthetic modules."""
        fdn = _load_fdn_conftest_module()
        original = sys.modules.get("card_impl")
        try:
            synth = types.ModuleType("card_impl")
            synth.__file__ = "<synthetic:fdn_conftest>"
            sys.modules["card_impl"] = synth
            assert fdn._has_explicit_card_impl() is False
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)

    def test_has_explicit_returns_false_when_no_card_impl(self) -> None:
        """_has_explicit_card_impl() returns False when card_impl is not in sys.modules."""
        fdn = _load_fdn_conftest_module()
        original = sys.modules.get("card_impl")
        try:
            sys.modules.pop("card_impl", None)
            assert fdn._has_explicit_card_impl() is False
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)

    def test_module_level_skips_injection_when_explicit_exists(self) -> None:
        """When explicit card_impl exists, conftest must not replace it."""
        original = sys.modules.get("card_impl")
        sentinel = types.ModuleType("card_impl")
        sentinel.__file__ = str(_PROJECT_ROOT / "pyproject.toml")
        sentinel._sentinel = True  # type: ignore[attr-defined]
        try:
            sys.modules["card_impl"] = sentinel
            conftest_path = _PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "conftest.py"
            spec = importlib.util.spec_from_file_location(
                "fdn_conftest_test_noinject", conftest_path,
                submodule_search_locations=[],
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert sys.modules["card_impl"] is sentinel
            assert getattr(sys.modules["card_impl"], "_sentinel", False) is True
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)


class TestSOSConftestBehavior:
    """Behavioral tests for SOS conftest stub handling."""

    def test_sos_error_module_raises_importerror_on_attr_access(self) -> None:
        """When stubs absent, error card_impl must raise ImportError on attr access."""
        sos = _load_sos_conftest_module()
        error_mod = sos._make_error_module("test error message")
        with pytest.raises(ImportError, match="test error message"):
            error_mod.__getattr__("SomeSOSCard")

    def test_sos_error_module_has_sos_file_marker(self) -> None:
        """Error module __file__ must contain 'sos_conftest'."""
        sos = _load_sos_conftest_module()
        error_mod = sos._make_error_module("stubs not available")
        assert "sos_conftest" in error_mod.__file__

    def test_sos_replaces_fdn_synthetic_with_sos_stubs(self) -> None:
        """SOS conftest must replace FDN synthetic card_impl with SOS stub module.

        Prevents SOS tests from accidentally using FDN card_impl. Since stubs
        are now available (Item 6), the conftest installs a proper stub-based
        card_impl instead of an error module.
        """
        original = sys.modules.get("card_impl")
        try:
            # Simulate FDN conftest having already installed synthetic module
            fdn_synth = types.ModuleType("card_impl")
            fdn_synth.__file__ = "<synthetic:fdn_conftest>"
            sys.modules["card_impl"] = fdn_synth

            conftest_path = _PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py"
            spec = importlib.util.spec_from_file_location(
                "sos_conftest_test_replace", conftest_path,
                submodule_search_locations=[],
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            current = sys.modules.get("card_impl")
            assert current is not None
            assert current.__file__ != "<synthetic:fdn_conftest>", (
                "SOS conftest must replace FDN synthetic card_impl"
            )
            # The installed module is now stub-based, so unknown card names
            # raise AttributeError (not ImportError).
            with pytest.raises(AttributeError):
                current.__getattr__("AnyCard")
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)

    def test_sos_conftest_references_register_sos_stubs(self) -> None:
        """SOS conftest must call register_sos_stubs() from benchmarks.sos.workspace.cards.stubs.sos_stubs."""
        content = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py").read_text()
        assert "register_sos_stubs" in content
        assert "benchmarks.sos.workspace.cards.stubs.sos_stubs" in content

    def test_sos_does_not_replace_real_explicit_card_impl(self) -> None:
        """SOS conftest must not replace an evaluator-provided real card_impl.py."""
        original = sys.modules.get("card_impl")
        sentinel = types.ModuleType("card_impl")
        sentinel.__file__ = str(_PROJECT_ROOT / "pyproject.toml")
        sentinel._sentinel = True  # type: ignore[attr-defined]
        try:
            sys.modules["card_impl"] = sentinel
            conftest_path = _PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / "conftest.py"
            spec = importlib.util.spec_from_file_location(
                "sos_conftest_test_nooverride", conftest_path,
                submodule_search_locations=[],
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert sys.modules["card_impl"] is sentinel
        finally:
            if original is not None:
                sys.modules["card_impl"] = original
            else:
                sys.modules.pop("card_impl", None)


class TestSamplePlainsTest:
    """Verify the sample Plains test under tests/audited/fdn/fdn_272/tests.py."""

    def test_plains_tests_file_imports_from_card_impl(self) -> None:
        tests_content = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272" / "tests.py").read_text()
        assert "from card_impl import Plains" in tests_content

    def test_plains_tests_file_has_test_class(self) -> None:
        tests_content = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272" / "tests.py").read_text()
        assert "class Test" in tests_content

    def test_plains_tests_file_has_category_markers(self) -> None:
        """Sample audited test should use pytest.mark category markers."""
        tests_content = (_PROJECT_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn" / "fdn_272" / "tests.py").read_text()
        assert "pytest.mark" in tests_content, (
            "Sample audited test should use pytest.mark category markers "
            "(@pytest.mark.basic, etc.) as per audited-test conventions"
        )


class TestWrongCardIsolation:
    """Verify that importing the wrong card class from a per-card directory fails clearly.

    This tests the stricter isolation rule: each audited test directory may only
    import the card mapped to its collector-number directory.
    """

    def test_fdn_wrong_class_import_raises_attributeerror(self) -> None:
        """Requesting 'Island' from collector dir 'fdn_272' (Plains) must raise AttributeError.

        The error message must clearly state what collector directory is active
        and what card it maps to.
        """
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)
        synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)

        # Simulate being inside collector dir fdn_272 by monkeypatching _detect_collector_dir
        import unittest.mock as mock
        with mock.patch.object(
            fdn, "_detect_collector_dir", return_value="fdn_272"
        ):
            # Rebind the module's closure to use the patched function
            synthetic_patched = fdn._make_card_impl_module(cn_to_entry, classname_to_class)
            with pytest.raises(AttributeError, match="fdn_272.*Plains.*Island"):
                synthetic_patched.__getattr__("Island")

    def test_fdn_wrong_class_error_mentions_isolation_rule(self) -> None:
        """Error message must tell the user each directory may only import its own card."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)

        import unittest.mock as mock
        with mock.patch.object(fdn, "_detect_collector_dir", return_value="fdn_272"):
            synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)
            with pytest.raises(AttributeError, match="only import its own card"):
                synthetic.__getattr__("Mountain")

    def test_fdn_unmapped_collector_dir_raises_attributeerror(self) -> None:
        """Requesting any class from an unmapped collector dir must raise AttributeError."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)

        import unittest.mock as mock
        with mock.patch.object(fdn, "_detect_collector_dir", return_value="999"):
            synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)
            with pytest.raises(AttributeError, match="999.*not mapped"):
                synthetic.__getattr__("Plains")


class TestFDNCollectorOverrideResolution:
    """Verify FDN Plains resolves via collector mapping despite missing registry metadata.

    Plains has an empty collector_number in registry metadata.  The conftest
    must use _COLLECTOR_DIR_OVERRIDES to map 'fdn_272' → Plains.
    """

    def test_plains_registry_has_empty_collector_number(self) -> None:
        """Confirm Plains' registry metadata lacks a collector_number (pre-condition)."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        _cls, meta = registry.get("Plains")
        assert not meta.collector_number, (
            "Plains should have empty collector_number in metadata — "
            "this test validates the override mechanism is needed"
        )

    def test_fdn_272_resolves_to_plains_via_override(self) -> None:
        """Collector dir 'fdn_272' must resolve to Plains via _COLLECTOR_DIR_OVERRIDES."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, _classname_to_class = fdn._build_collector_maps(registry)
        assert "fdn_272" in cn_to_entry, (
            "Collector dir 'fdn_272' must be in cn_to_entry despite empty "
            "registry collector_number — _COLLECTOR_DIR_OVERRIDES should provide it"
        )
        impl_class, card_name = cn_to_entry["fdn_272"]
        assert card_name == "Plains"
        assert impl_class.__name__ == "Plains"

    def test_fdn_272_synthetic_module_resolves_plains_class(self) -> None:
        """Synthetic card_impl for dir 'fdn_272' must return the Plains class."""
        fdn = _load_fdn_conftest_module()
        registry = fdn._build_registry()
        cn_to_entry, classname_to_class = fdn._build_collector_maps(registry)

        import unittest.mock as mock
        with mock.patch.object(fdn, "_detect_collector_dir", return_value="fdn_272"):
            synthetic = fdn._make_card_impl_module(cn_to_entry, classname_to_class)
            plains_cls = synthetic.__getattr__("Plains")
            assert plains_cls.__name__ == "Plains"

    def test_all_basic_lands_have_overrides(self) -> None:
        """All five basic lands must have override entries keyed by cards/fdn dir name."""
        fdn = _load_fdn_conftest_module()
        overrides = fdn._COLLECTOR_DIR_OVERRIDES
        expected = {"fdn_272": "Plains", "fdn_274": "Island", "fdn_276": "Swamp",
                    "fdn_278": "Mountain", "fdn_280": "Forest"}
        for cn, name in expected.items():
            assert cn in overrides, f"Override missing for {cn} ({name})"
            assert overrides[cn] == name


class TestSOSSetPrefixedResolution:
    """Verify SOS set-prefixed directories (soa_1, spg_149) resolve distinctly.

    When a fake cards.stubs.sos_stubs module registers stubs with set_code
    metadata, the SOS conftest must create set-prefixed lookup entries so that
    soa_1 and spg_149 resolve to different cards, even if their plain collector
    numbers would collide.
    """

    def _make_fake_sos_stubs_module(self) -> types.ModuleType:
        """Create a fake cards.stubs.sos_stubs with register_sos_stubs().

        Registers three stub cards:
        - SOS base card cn=1, set_code="sos" → dir "1" (no prefix)
        - SOA card cn=1, set_code="soa" → dir "soa_1"
        - SPG card cn=149, set_code="spg" → dir "spg_149"
        """
        from benchmarks.sos.workspace.cards.registry import CardRegistry, CardMetadata
        from benchmarks.sos.workspace.engine.card import CardImpl

        # Create distinct stub classes
        SOSBaseCard = type("SOSBaseCard", (CardImpl,), {"__init__": lambda self, **kw: None})
        SOAArchiveCard = type("SOAArchiveCard", (CardImpl,), {"__init__": lambda self, **kw: None})
        SPGGuestCard = type("SPGGuestCard", (CardImpl,), {"__init__": lambda self, **kw: None})

        def register_sos_stubs(registry: CardRegistry) -> None:
            registry.register(
                "SOS Base Card",
                SOSBaseCard,
                CardMetadata(collector_number="1", set_code="sos"),
            )
            registry.register(
                "SOA Archive Card",
                SOAArchiveCard,
                CardMetadata(collector_number="1", set_code="soa"),
            )
            registry.register(
                "SPG Guest Card",
                SPGGuestCard,
                CardMetadata(collector_number="149", set_code="spg"),
            )

        fake_mod = types.ModuleType("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        fake_mod.register_sos_stubs = register_sos_stubs
        return fake_mod

    def test_soa_prefix_maps_distinctly_from_sos_prefix(self) -> None:
        """'soa_1' and 'sos_1' must map to different cards (SOA vs SOS base)."""
        sos = _load_sos_conftest_module()
        fake_stubs = self._make_fake_sos_stubs_module()

        original_stubs = sys.modules.get("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        try:
            sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = fake_stubs
            cn_to_entry, _classname_to_class = sos._load_sos_stubs_and_build_registry()

            assert "sos_1" in cn_to_entry, "Set-prefixed 'sos_1' must map to SOS base card"
            assert "soa_1" in cn_to_entry, "Set-prefixed 'soa_1' must map to SOA card"

            sos_class, sos_name = cn_to_entry["sos_1"]
            soa_class, soa_name = cn_to_entry["soa_1"]
            # They must resolve to different classes
            assert soa_class is not sos_class, (
                "soa_1 and sos_1 must map to different classes"
            )
        finally:
            if original_stubs is not None:
                sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = original_stubs
            else:
                sys.modules.pop("benchmarks.sos.workspace.cards.stubs.sos_stubs", None)

    def test_spg_prefix_maps_correctly(self) -> None:
        """'spg_149' must map to the SPG guest card."""
        sos = _load_sos_conftest_module()
        fake_stubs = self._make_fake_sos_stubs_module()

        original_stubs = sys.modules.get("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        try:
            sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = fake_stubs
            cn_to_entry, _classname_to_class = sos._load_sos_stubs_and_build_registry()

            assert "spg_149" in cn_to_entry, "Set-prefixed 'spg_149' must exist"
            spg_class, spg_name = cn_to_entry["spg_149"]
            assert spg_class.__name__ == "SPGGuestCard"
        finally:
            if original_stubs is not None:
                sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = original_stubs
            else:
                sys.modules.pop("benchmarks.sos.workspace.cards.stubs.sos_stubs", None)

    def test_sos_base_card_uses_set_prefix(self) -> None:
        """SOS base set cards (set_code='sos') must use the 'sos_N' prefixed form."""
        sos = _load_sos_conftest_module()
        fake_stubs = self._make_fake_sos_stubs_module()

        original_stubs = sys.modules.get("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        try:
            sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = fake_stubs
            cn_to_entry, _classname_to_class = sos._load_sos_stubs_and_build_registry()

            # sos_1 must exist — SOS base cards use set-prefixed dirs to match cards/sos/
            assert "sos_1" in cn_to_entry, (
                "SOS base cards must use set-prefixed dirs (e.g. 'sos_1')"
            )
            # Plain numeric '1' must NOT exist — directories now mirror cards/sos/sos_N
            assert "1" not in cn_to_entry, (
                "Plain numeric '1' must not exist — base SOS cards use sos_N format"
            )
        finally:
            if original_stubs is not None:
                sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = original_stubs
            else:
                sys.modules.pop("benchmarks.sos.workspace.cards.stubs.sos_stubs", None)

    def test_sos_synthetic_resolves_soa_card_from_prefixed_dir(self) -> None:
        """Synthetic card_impl with detected dir 'soa_1' must return SOA card class."""
        sos = _load_sos_conftest_module()
        fake_stubs = self._make_fake_sos_stubs_module()

        original_stubs = sys.modules.get("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        try:
            sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = fake_stubs
            cn_to_entry, classname_to_class = sos._load_sos_stubs_and_build_registry()
            synthetic = sos._make_card_impl_module(cn_to_entry, classname_to_class)

            import unittest.mock as mock
            with mock.patch.object(sos, "_detect_collector_dir", return_value="soa_1"):
                synthetic = sos._make_card_impl_module(cn_to_entry, classname_to_class)
                result = synthetic.__getattr__("SOAArchiveCard")
                assert result.__name__ == "SOAArchiveCard"
        finally:
            if original_stubs is not None:
                sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = original_stubs
            else:
                sys.modules.pop("benchmarks.sos.workspace.cards.stubs.sos_stubs", None)

    def test_sos_synthetic_rejects_wrong_card_from_prefixed_dir(self) -> None:
        """Importing wrong class from 'soa_1' dir must raise AttributeError."""
        sos = _load_sos_conftest_module()
        fake_stubs = self._make_fake_sos_stubs_module()

        original_stubs = sys.modules.get("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        try:
            sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = fake_stubs
            cn_to_entry, classname_to_class = sos._load_sos_stubs_and_build_registry()

            import unittest.mock as mock
            with mock.patch.object(sos, "_detect_collector_dir", return_value="soa_1"):
                synthetic = sos._make_card_impl_module(cn_to_entry, classname_to_class)
                with pytest.raises(AttributeError, match="soa_1.*SOAArchiveCard"):
                    synthetic.__getattr__("SPGGuestCard")
        finally:
            if original_stubs is not None:
                sys.modules["benchmarks.sos.workspace.cards.stubs.sos_stubs"] = original_stubs
            else:
                sys.modules.pop("benchmarks.sos.workspace.cards.stubs.sos_stubs", None)


class TestPlainsTestExecution:
    """Actually run Plains resolution to verify end-to-end infrastructure."""

    def test_plains_is_land_subclass(self) -> None:
        from benchmarks.sos.workspace.cards.registry import CardRegistry
        from benchmarks.sos.workspace.engine.basic_lands import register_basic_lands
        from benchmarks.sos.workspace.engine.card import Land

        registry = CardRegistry()
        register_basic_lands(registry)
        plains_cls, _meta = registry.get("Plains")
        card = plains_cls(name="Plains", owner=None)
        assert isinstance(card, Land)

    def test_plains_has_mana_abilities(self) -> None:
        from benchmarks.sos.workspace.cards.registry import CardRegistry
        from benchmarks.sos.workspace.engine.basic_lands import register_basic_lands

        registry = CardRegistry()
        register_basic_lands(registry)
        plains_cls, _meta = registry.get("Plains")
        card = plains_cls(name="Plains", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) > 0
        assert any("{W}" in a.description for a in abilities)
