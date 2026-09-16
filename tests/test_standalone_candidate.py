import hashlib
import json

import pytest
from karn.definition import canonical, new_definition

from silverquillm.candidate import (
    CandidateRefusedError,
    CandidateVendorError,
    ImageBuildError,
    build_candidate_image,
    load_candidate_bundle,
    vendor_candidate,
)
from silverquillm.results_repo import CandidateIdentity, candidate_hash

IMAGE = "sha256:" + "1" * 64


def definition_file(tmp_path, *, name="candidate", environment=None):
    definition = new_definition(
        name=name, mode="automaton", image=IMAGE, main=["/bin/true"], definition_version=3
    )
    document = definition.document
    document["runtime"]["environment"] = environment or {}
    path = tmp_path / (name + ".json")
    path.write_bytes(canonical(document))
    return path


def test_different_manifests_share_an_immutable_local_image(tmp_path):
    first = load_candidate_bundle(definition_file(tmp_path, name="one"))
    second = load_candidate_bundle(
        definition_file(tmp_path, name="two", environment={"CHOICE": "two"})
    )
    assert first.identity.image_digest == second.identity.image_digest == IMAGE
    assert first.candidate_hash != second.candidate_hash
    for candidate in (first, second):
        image = build_candidate_image(candidate, inspector=lambda _: {"Id": IMAGE, "Os": "linux"})
        assert image.image_id == IMAGE
        assert CandidateIdentity.from_dict(candidate.identity.to_dict()) == candidate.identity


def test_image_mismatch_and_unsupported_wire_are_refused(tmp_path):
    path = definition_file(tmp_path)
    candidate = load_candidate_bundle(path)
    with pytest.raises(ImageBuildError):
        build_candidate_image(
            candidate, inspector=lambda _: {"Id": "sha256:" + "2" * 64, "Os": "linux"}
        )
    document = candidate.manifest
    document["definition_version"] = 99
    path.write_bytes(canonical(document))
    with pytest.raises(CandidateRefusedError):
        load_candidate_bundle(path)


def test_vendor_is_write_once_and_checks_existing_definition(tmp_path):
    candidate = load_candidate_bundle(definition_file(tmp_path))
    repo = tmp_path / "results"
    result = vendor_candidate(repo, candidate)
    assert result.written
    assert not vendor_candidate(repo, candidate).written
    path = result.path / "definition.json"
    document = candidate.manifest
    document["name"] = "tampered"
    path.write_bytes(canonical(document))
    with pytest.raises(CandidateVendorError):
        vendor_candidate(repo, candidate)


def test_historical_hashes_are_byte_compatible():
    old = CandidateIdentity.recomputed(IMAGE, "2" * 64, "arbitrary-adapter")
    payload = {"adapter": "arbitrary-adapter", "base_digest": IMAGE, "instruction_hash": "2" * 64}
    assert (
        candidate_hash(old)
        == hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert CandidateIdentity.from_dict(old.to_dict()) == old
    legacy = CandidateIdentity.legacy("original-image")
    assert candidate_hash(legacy) == "original-image"
    assert CandidateIdentity.from_dict(legacy.to_dict()) == legacy


def test_historical_bundle_is_not_silently_reinterpreted(tmp_path):
    (tmp_path / "candidate.json").write_text("{}")
    with pytest.raises(CandidateRefusedError, match="historical"):
        load_candidate_bundle(tmp_path)


def test_candidate_import_does_not_load_ozolith_packages():
    import sys

    assert not any(name.startswith(("theozolith_", "ozolith_")) for name in sys.modules)
