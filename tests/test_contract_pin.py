"""Versioned Karn definitions need no Ozolith package or package-tree proof."""

import importlib.util
import tomllib
from pathlib import Path

import pytest
from karn.definition import canonical, new_definition

from silverquillm.contract_version import SUPPORTED_DEFINITION_VERSIONS, check_contract_support


@pytest.mark.parametrize("version", SUPPORTED_DEFINITION_VERSIONS)
def test_each_explicit_definition_version_is_decoded_without_reinterpretation(version):
    value = new_definition(
        name="fixture",
        mode="automaton",
        image="sha256:" + "a" * 64,
        main=["/bin/true"],
        definition_version=version,
    )
    assert check_contract_support(value.encoded).document["definition_version"] == version


def test_unknown_definition_version_refuses():
    value = new_definition(
        name="fixture", mode="automaton", image="sha256:" + "a" * 64, main=["/bin/true"]
    ).document
    value["definition_version"] = 999
    with pytest.raises(ValueError):
        check_contract_support(canonical(value))


def test_no_ozolith_package_is_required_or_installed():
    config = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert not any("ozolith" in item.lower() for item in config["project"]["dependencies"])
    for name in (
        "theozolith_worker",
        "theozolith_control",
        "theozolith_nodedaemon",
        "theozolith_knowledge",
    ):
        assert importlib.util.find_spec(name) is None
