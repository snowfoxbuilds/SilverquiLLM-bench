"""Explicit native reference definitions and unchanged historical candidate identity."""

import json
from pathlib import Path

import pytest

from silverquillm.candidate import load_candidate_bundle, scan_tree_for_credentials
from silverquillm.promotion import verify_source
from silverquillm.results_repo import CandidateIdentity, candidate_hash

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "candidates"
HISTORICAL = {"vanilla-claude--4e8b75b6", "vanilla-codex--90a33424"}


def _candidate_dirs(root=CANDIDATES):
    found = []
    for path in sorted(root.iterdir()):
        if path.name.startswith("."):
            continue
        assert not path.is_symlink(), "curated candidates cannot be symlinks"
        if path.is_dir():
            found.append(path)
    return found


@pytest.mark.parametrize("path", _candidate_dirs(), ids=lambda path: path.name)
def test_every_curated_candidate_has_explicit_current_or_historical_identity(path):
    if path.name in HISTORICAL:
        doc = json.loads((path / "bundle/candidate.json").read_text())
        identity = CandidateIdentity.recomputed(
            doc["base_digest"], doc["instruction_hash"], doc["adapter"]
        )
        assert path.name.endswith("--" + candidate_hash(identity)[:8])
        assert not (path / "bundle/definition.json").exists()
    else:
        candidate = verify_source(path)
        assert path.name.endswith("--" + candidate.hash8)
        assert candidate.definition.digest in (path / "README.md").read_text()
        assert not scan_tree_for_credentials(path, secret_slots=candidate.secret_slots)
        assert candidate.manifest["runtime"]["main"][:2] == ["python3", "/opt/benchmark/adapter.py"]


def test_both_real_native_references_are_explicit_and_distinct():
    current = [
        load_candidate_bundle(path) for path in _candidate_dirs() if path.name not in HISTORICAL
    ]
    assert {row.worker_type for row in current} == {
        "vanilla-claude-standalone",
        "vanilla-codex-standalone",
    }
    assert len({row.candidate_hash for row in current}) == 2
    for row in current:
        assert "--check" not in row.manifest["runtime"]["main"]
        assert row.manifest["runtime"]["credentials"]
        assert row.manifest["runtime"]["bootstrap"]["protocol"] == "identity-v2"
        assert all(not mount["persistent"] for mount in row.manifest["runtime"]["mounts"])


def test_discovery_refuses_symlinked_curated_entries(tmp_path):
    (tmp_path / "alias").symlink_to(next(iter(_candidate_dirs())), target_is_directory=True)
    with pytest.raises(AssertionError, match="symlinks"):
        _candidate_dirs(tmp_path)


def test_native_reference_build_inputs_match_recorded_source_inventory():
    import hashlib
    for path in _candidate_dirs():
        if path.name in HISTORICAL:
            continue
        record = json.loads((path / "reference-build.json").read_text())
        candidate = load_candidate_bundle(path)
        assert record["image"] == candidate.manifest["image"]
        for name, digest in record["build_source"]["files"].items():
            assert Path(name).name == name
            assert hashlib.sha256((ROOT / "reference-recipes" / name).read_bytes()).hexdigest() == digest
        delivery = candidate.manifest["runtime"]["credentials"][0]
        if "codex" in candidate.worker_type:
            assert delivery["source"]["secret"] == "openai-api-key"
            assert delivery["delivery"]["variable"] == "CODEX_API_KEY"
        else:
            assert delivery["source"]["secret"] == "anthropic-api-key"
            assert delivery["delivery"]["variable"] == "ANTHROPIC_API_KEY"
