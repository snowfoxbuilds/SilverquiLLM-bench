"""Run Record identity and batch formats across Karn Construct Definition versions 4 and 5."""

from __future__ import annotations

import pytest

from silverquillm.karn.batching import FORMAT, FORMATS, load_batch, queue_rows
from silverquillm.karn.definition import SCHEMES
from silverquillm.karn.records import KarnIdentity
from silverquillm.results_repo import KARN_SCHEMES, InvalidRunRecordError


def identity(**changes):
    return {
        "scheme": "karn-v5",
        "definition_version": 5,
        "definition_id": "8b1bd7a7-4bd8-5d6f-a1b9-1e0b8a2c6f3d",
        "definition_digest": "sha256:" + "a" * 64,
        "image": "sha256:" + "b" * 64,
        "image_id": "sha256:" + "b" * 64,
        **changes,
    }


@pytest.mark.parametrize(("scheme", "version"), [("karn-v4", 4), ("karn-v5", 5)])
def test_each_scheme_pairs_with_its_definition_version(scheme, version):
    value = identity(scheme=scheme, definition_version=version)
    assert KarnIdentity.from_dict(value).to_dict() == value


@pytest.mark.parametrize(
    ("scheme", "version"),
    [
        ("karn-v4", 5),
        ("karn-v5", 4),
        ("karn-v5", True),
        ("karn-v5", 5.0),
        ("karn-v6", 6),
        (None, 6),
        ("karn-v5", "5"),
    ],
)
def test_mismatched_scheme_and_version_are_refused(scheme, version):
    with pytest.raises(InvalidRunRecordError):
        KarnIdentity.from_dict(identity(scheme=scheme, definition_version=version))


def test_results_repository_knows_every_karn_scheme():
    assert KARN_SCHEMES == set(SCHEMES.values())


def batch(directory, name, format):
    path = directory / f"{name}.toml"
    path.write_text(
        f'format = "{format}"\n[[runs]]\nbuild_output = "b"\nconstruct = "bare"\nbenchmark = "smoke"\n'
    )
    return path


def test_new_batches_are_karn_v5_and_karn_v4_batches_still_load(tmp_path):
    assert FORMAT == "karn-v5" and FORMATS == ("karn-v4", "karn-v5")
    for format in FORMATS:
        assert load_batch(batch(tmp_path, format, format))["format"] == format


def test_queue_reports_each_batch_in_its_own_format(tmp_path):
    batch(tmp_path, "old", "karn-v4")
    batch(tmp_path, "new", "karn-v5")
    rows = {row["batch"]: row["format"] for row in queue_rows(tmp_path)}
    assert rows == {"new": "karn-v5", "old": "karn-v4"}
