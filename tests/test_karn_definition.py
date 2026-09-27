from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.karn.definition import (
    KarnError,
    canonical,
    decode_definition,
    digest,
    load_candidate,
)

VECTORS = Path(__file__).parent / "fixtures/karn/wire-vectors-v4"


def definition():
    value = json.loads((VECTORS / "canonical-definition-id/input.json").read_bytes())
    value["runtime"]["plugins"] = []
    return value


def built(tmp_path, value=None):
    value = definition() if value is None else value
    path = tmp_path / "constructs/bare/definition.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return value, path


def inspector(reference):
    return {"Id": reference, "RepoDigests": []}


@pytest.mark.parametrize("vector", sorted(VECTORS.iterdir()), ids=lambda p: p.name)
def test_producer_golden_vectors(vector):
    raw = (vector / "input.json").read_bytes()
    if (vector / "error.txt").exists():
        with pytest.raises(KarnError):
            decode_definition(raw)
    else:
        encoded = canonical(decode_definition(raw))
        assert encoded == (vector / "canonical.bytes").read_bytes()
        assert digest(encoded) == (vector / "digest.txt").read_text().strip()


def test_records_complete_definition_independently_of_image(tmp_path):
    value, path = built(tmp_path)
    first = load_candidate(tmp_path, "bare", image_inspector=inspector)
    value["runtime"]["environment"]["CONSTRUCT_MODEL"] = "new-model"
    path.write_bytes(canonical(value))
    second = load_candidate(tmp_path, "bare", image_inspector=inspector)
    assert first.image_id == second.image_id
    assert first.definition_id == second.definition_id
    assert first.definition_digest != second.definition_digest
    with pytest.raises(KarnError, match="candidate_artifact_changed"):
        first.verify()


def test_mutating_in_memory_selection_cannot_change_what_runs(tmp_path):
    built(tmp_path)
    candidate = load_candidate(tmp_path, "bare", image_inspector=inspector)
    candidate.runtime["main"] = ["different-program"]
    with pytest.raises(KarnError, match="candidate_definition_changed"):
        candidate.verify()


def test_wrong_image_is_not_admitted(tmp_path):
    built(tmp_path)
    with pytest.raises(KarnError, match="image_identity_mismatch"):
        load_candidate(tmp_path, "bare", image_inspector=lambda _: {"Id": "sha256:" + "9" * 64})


def test_repository_digest_resolves_and_records_engine_image_id(tmp_path):
    value = definition()
    value["image"] = "example.test/candidate@sha256:" + "3" * 64
    built(tmp_path, value)
    candidate = load_candidate(
        tmp_path,
        "bare",
        image_inspector=lambda _: {
            "Id": "sha256:" + "4" * 64,
            "RepoDigests": [value["image"]],
        },
    )
    assert candidate.image_id == "sha256:" + "4" * 64


def test_schema_and_file_paths_are_validated(tmp_path):
    value = definition()
    value["runtime"]["mounts"] = [
        {
            "name": "input",
            "target": "/input",
            "source": {"kind": "runtime", "value": "input"},
            "persistent": False,
            "access": "read_only",
            "purpose": "input",
        }
    ]
    value["runtime"]["files"] = [
        {
            "name": "prompt",
            "mount": "input",
            "path": "../../outside",
            "direction": "input",
            "schema": {},
        }
    ]
    built(tmp_path, value)
    with pytest.raises(KarnError, match="unsafe_artifact_path"):
        load_candidate(tmp_path, "bare", image_inspector=inspector)


def plugin_build(tmp_path):
    value = definition()
    directory = tmp_path / "plugins/karn-codex-login-0.1.0"
    directory.mkdir(parents=True)
    wheel = directory / "karn_codex_login-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"test wheel content")
    manifest = {
        "id": "karn-codex-login",
        "version": "0.1.0",
        "sdk_major": 1,
        "python": "3.13",
        "module": "karn_codex_login",
        "hooks": ["before_container_mount"],
        "wheels": {wheel.name: digest(wheel.read_bytes())},
    }
    (directory / "install.json").write_bytes(
        canonical({"manifest": manifest, "locations": {wheel.name: wheel.name}})
    )
    value["runtime"]["plugins"] = [
        {
            "id": manifest["id"],
            "version": manifest["version"],
            "source": "catalog",
            "artifact": digest(canonical(manifest, ascii_only=True)),
        }
    ]
    built(tmp_path, value)
    return wheel


def test_plugin_artifact_binds_complete_wheel_closure(tmp_path):
    wheel = plugin_build(tmp_path)
    candidate = load_candidate(tmp_path, "bare", image_inspector=inspector)
    assert len(candidate.plugins) == 1
    wheel.write_bytes(b"replaced wheel")
    with pytest.raises(KarnError, match="plugin_wheel_digest_mismatch"):
        candidate.verify()


def test_install_document_cannot_follow_symlink_outside_build(tmp_path):
    wheel = plugin_build(tmp_path)
    outside = tmp_path / "other.whl"
    wheel.rename(outside)
    wheel.symlink_to(outside)
    with pytest.raises(KarnError, match="symlink_artifact_path"):
        load_candidate(tmp_path, "bare", image_inspector=inspector)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_loose_input_encodings_canonicalize_like_karn(encoding):
    value = definition()
    assert canonical(decode_definition(json.dumps(value).encode(encoding))) == canonical(value)
