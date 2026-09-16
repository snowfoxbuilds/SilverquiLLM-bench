"""Supported Karn definitions and benchmark-owned comparison interface versions."""

from karn.definition import Definition, decode

SUPPORTED_DEFINITION_VERSIONS = (1, 2, 3)
BENCHMARK_INTERFACE_VERSION = 1
PROPOSAL_SCHEMA_VERSION = 1


class UnsupportedContractError(ValueError):
    pass


def check_contract_support(definition):
    selected = definition if isinstance(definition, Definition) else decode(definition)
    if selected.document["definition_version"] not in SUPPORTED_DEFINITION_VERSIONS:
        raise UnsupportedContractError("unsupported Construct Definition version")
    return selected
