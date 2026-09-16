"""Atomic standalone definition promotion, public source proof and cleanup failures."""

import shutil
import subprocess

import pytest

from silverquillm import promotion
from silverquillm.candidate import CandidateRefusedError
from tests.candidate_fixtures import FAKE_CREDENTIALS, make_source


def source(tmp_path):
    return make_source(tmp_path)


def test_promotion_is_source_reproducible_atomic_and_git_agnostic(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("promotion must not launch a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    root = tmp_path / "candidates"
    result = promotion.promote(source(tmp_path), candidates_dir=root)
    assert result.written and list(root.iterdir()) == [result.candidate_dir]
    assert promotion.verify_source(result.candidate_dir).identity == result.bundle.identity
    assert (result.candidate_dir / "source/definition.json").read_bytes() == (
        result.candidate_dir / "bundle/definition.json"
    ).read_bytes()
    assert str(tmp_path) not in (result.candidate_dir / "README.md").read_text()
    repeated = promotion.promote(source(tmp_path), candidates_dir=root)
    assert not repeated.written


@pytest.mark.parametrize(
    "target", ["source/definition.json", "source.json", "bundle/definition.json"]
)
def test_tampered_existing_source_is_refused_without_repair(tmp_path, target):
    candidate = source(tmp_path)
    result = promotion.promote(candidate, candidates_dir=tmp_path / "candidates")
    path = result.candidate_dir / target
    path.write_text("tampered")
    with pytest.raises((promotion.PromotionRefused, CandidateRefusedError)):
        promotion.promote(candidate, candidates_dir=tmp_path / "candidates")
    assert path.read_text() == "tampered"


@pytest.mark.parametrize("value", list(FAKE_CREDENTIALS.values()))
def test_whole_tree_secret_scan_includes_public_readme(tmp_path, value):
    result = promotion.promote(source(tmp_path), candidates_dir=tmp_path / "candidates")
    (result.candidate_dir / "README.md").write_text(value)
    with pytest.raises(promotion.PromotionRefused) as error:
        promotion.verify_source(result.candidate_dir)
    assert value not in str(error.value)


def test_unlisted_source_file_and_symlink_are_refused(tmp_path):
    result = promotion.promote(source(tmp_path), candidates_dir=tmp_path / "candidates")
    extra = result.candidate_dir / "source/extra"
    extra.write_text("unlisted")
    with pytest.raises(promotion.PromotionRefused):
        promotion.verify_source(result.candidate_dir)
    extra.unlink()
    path = result.candidate_dir / "source/definition.json"
    path.unlink()
    path.symlink_to(result.candidate_dir / "bundle/definition.json")
    with pytest.raises(promotion.PromotionRefused):
        promotion.verify_source(result.candidate_dir)


@pytest.mark.parametrize("slug", ["../bad", "/absolute", ".", "two--parts"])
def test_invalid_slug_refuses_before_any_directory_is_created(tmp_path, slug):
    candidate = source(tmp_path)
    root = tmp_path / "absent/candidates"
    with pytest.raises(promotion.PromotionRefused):
        promotion.promote(candidate, candidates_dir=root, slug=slug)
    assert not root.parent.exists()


def test_dry_run_is_strictly_read_only(tmp_path):
    candidate = source(tmp_path)
    root = tmp_path / "absent/candidates"
    result = promotion.promote(candidate, candidates_dir=root, dry_run=True)
    assert not result.written and not root.parent.exists()


def test_identity_cannot_be_promoted_twice_under_different_names(tmp_path):
    candidate = source(tmp_path)
    root = tmp_path / "candidates"
    first = promotion.promote(candidate, candidates_dir=root, slug="one")
    with pytest.raises(promotion.PromotionRefused, match="another curated name"):
        promotion.promote(candidate, candidates_dir=root, slug="two")
    assert list(root.iterdir()) == [first.candidate_dir]


def test_staging_failure_restores_only_created_directories(tmp_path, monkeypatch):
    candidate = source(tmp_path)
    root = tmp_path / "absent/candidates"
    monkeypatch.setattr(
        promotion.tempfile,
        "mkdtemp",
        lambda **kw: (_ for _ in ()).throw(OSError("fixture failure")),
    )
    with pytest.raises(OSError):
        promotion.promote(candidate, candidates_dir=root)
    assert not root.parent.exists()
    root.mkdir(parents=True)
    with pytest.raises(OSError):
        promotion.promote(candidate, candidates_dir=root)
    assert root.is_dir() and not list(root.iterdir())


def test_refused_staging_cleanup_failure_is_loud_and_releases_lock(tmp_path, monkeypatch):
    candidate = source(tmp_path)
    root = tmp_path / "candidates"
    monkeypatch.setattr(
        promotion,
        "verify_source",
        lambda *a, **kw: (_ for _ in ()).throw(promotion.PromotionRefused("fixture refusal")),
    )
    original = shutil.rmtree
    monkeypatch.setattr(
        shutil, "rmtree", lambda *a, **kw: (_ for _ in ()).throw(OSError("fixture cleanup failure"))
    )
    with pytest.raises(promotion.PromotionCleanupError, match="KEPT"):
        promotion.promote(candidate, candidates_dir=root)
    assert any(p.name.startswith(".promote-") for p in root.iterdir())
    import fcntl
    import os

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)
    monkeypatch.setattr(shutil, "rmtree", original)
    original(root)
