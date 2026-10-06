"""Platform Tests for ``scripts/port_from_known_best.py`` (KNOWN-BEST-ENGINE.md › Building a benchmark from it)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.port_from_known_best import PortError, apply_patch, check, defect_patches

REPO = Path(__file__).resolve().parents[1]
PATCH = """\
--- a/engine/rules.py
+++ b/engine/rules.py
@@ -2,3 +2,3 @@
 def untap(obj):
-    if not obj.skip_untap:
+    if True:
         obj.is_tapped = False
"""


def _tree(tmp_path: Path, text: str) -> Path:
    (tmp_path / "engine").mkdir(parents=True)
    (tmp_path / "engine/rules.py").write_text(text)
    return tmp_path


def _patch(tmp_path: Path, text: str = PATCH) -> Path:
    patch = tmp_path / "defect.patch"
    patch.write_text(text)
    return patch


def test_patch_applies_with_exact_context(tmp_path: Path) -> None:
    tree = _tree(tmp_path / "t", "import x\ndef untap(obj):\n    if not obj.skip_untap:\n        obj.is_tapped = False\n")
    apply_patch(tree, _patch(tmp_path))
    assert (tree / "engine/rules.py").read_text() == (
        "import x\ndef untap(obj):\n    if True:\n        obj.is_tapped = False\n"
    )


def test_patch_follows_code_that_moved(tmp_path: Path) -> None:
    moved = "import x\n" * 10 + "def untap(obj):\n    if not obj.skip_untap:\n        obj.is_tapped = False\n"
    tree = _tree(tmp_path / "t", moved)
    apply_patch(tree, _patch(tmp_path))
    assert "    if True:\n" in (tree / "engine/rules.py").read_text()


def test_patch_that_no_longer_applies_fails_loudly(tmp_path: Path) -> None:
    tree = _tree(tmp_path / "t", "def untap(obj):\n    obj.is_tapped = False\n")
    with pytest.raises(PortError, match="does not apply"):
        apply_patch(tree, _patch(tmp_path))


def test_patch_can_add_a_file(tmp_path: Path) -> None:
    tree = _tree(tmp_path / "t", "")
    apply_patch(tree, _patch(tmp_path, "--- /dev/null\n+++ b/engine/new.py\n@@ -0,0 +1,2 @@\n+a = 1\n+b = 2\n"))
    assert (tree / "engine/new.py").read_text() == "a = 1\nb = 2\n"


def _benchmark(tmp_path: Path, ids: list[str], patches: list[str]) -> Path:
    root = tmp_path / "bench"
    (root / "data/known_defects").mkdir(parents=True)
    manifest = {"defects": [{"id": defect_id} for defect_id in ids]}
    (root / "data/known_defects.json").write_text(json.dumps(manifest))
    for name in patches:
        (root / "data/known_defects" / f"{name}.patch").write_text(PATCH)
    return root


def test_defect_patches_follow_manifest_order(tmp_path: Path) -> None:
    root = _benchmark(tmp_path, ["b-defect", "a-defect"], ["a-defect", "b-defect"])
    assert [p.stem for p in defect_patches(root)] == ["b-defect", "a-defect"]


def test_every_known_defect_needs_a_patch(tmp_path: Path) -> None:
    with pytest.raises(PortError, match="without a patch"):
        defect_patches(_benchmark(tmp_path, ["a-defect", "b-defect"], ["a-defect"]))


def test_a_patch_must_belong_to_a_listed_defect(tmp_path: Path) -> None:
    with pytest.raises(PortError, match="no listed Known Defect"):
        defect_patches(_benchmark(tmp_path, ["a-defect"], ["a-defect", "stray"]))


def test_smoke_is_ported_from_the_known_best_workspace() -> None:
    """Re-porting smoke changes nothing: its Workspace is the Known-Best Workspace
    plus its target stubs and Known Defect patches, and its oracle and Audited
    Tests are the Known-Best copies."""
    assert check(REPO / "benchmarks/smoke") == []


# ---------------------------------------------------------------------------
# The patch format is enforced, and a failing patch changes nothing
# ---------------------------------------------------------------------------


def _files(tmp_path: Path, **files: str) -> Path:
    tree = tmp_path / "t"
    for name, text in files.items():
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text(text)
    return tree


def test_a_hunk_shorter_than_its_declared_counts_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "x = 1\ny = 2\nz = 3\n"})
    patch = _patch(tmp_path, "--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 3\n")
    with pytest.raises(PortError, match="declared"):
        apply_patch(tree, patch)
    assert (tree / "a.py").read_text() == "x = 1\ny = 2\nz = 3\n"


def test_a_file_header_without_hunks_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "x = 1\n"})
    with pytest.raises(PortError, match="without hunks"):
        apply_patch(tree, _patch(tmp_path, "--- a/a.py\n+++ b/a.py\n"))


def test_an_unpaired_file_header_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "x = 1\n"})
    with pytest.raises(PortError, match="without its"):
        apply_patch(tree, _patch(tmp_path, "--- a/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"))


def test_a_zero_length_old_range_inserts_after_its_line(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "a\nb\n"})
    apply_patch(tree, _patch(tmp_path, "--- a/a.py\n+++ b/a.py\n@@ -1,0 +2 @@\n+new\n"))
    assert (tree / "a.py").read_text() == "a\nnew\nb\n"


def test_a_zero_length_old_range_at_the_top_inserts_first(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "a\n"})
    apply_patch(tree, _patch(tmp_path, "--- a/a.py\n+++ b/a.py\n@@ -0,0 +1 @@\n+new\n"))
    assert (tree / "a.py").read_text() == "new\na\n"


def test_a_deletion_that_would_leave_content_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "old = 1\nnew = 2\n"})
    patch = _patch(tmp_path, "--- a/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old = 1\n")
    with pytest.raises(PortError, match="leave content"):
        apply_patch(tree, patch)
    assert (tree / "a.py").read_text() == "old = 1\nnew = 2\n"


def test_a_deletion_of_exactly_the_file_content_deletes_it(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "old = 1\n"})
    apply_patch(tree, _patch(tmp_path, "--- a/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old = 1\n"))
    assert not (tree / "a.py").exists()


@pytest.mark.parametrize("path", ["../outside.py", "a/../../outside.py"])
def test_a_path_that_climbs_out_of_the_tree_is_rejected(tmp_path: Path, path: str) -> None:
    tree = _files(tmp_path, **{"inside.py": "x = 1\n"})
    outside = tmp_path / "outside.py"
    outside.write_text("old = True\n")
    patch = _patch(tmp_path, f"--- {path}\n+++ {path}\n@@ -1 +1 @@\n-old = True\n+old = False\n")
    with pytest.raises(PortError, match="not relative|leads out"):
        apply_patch(tree, patch)
    assert outside.read_text() == "old = True\n"


def test_an_absolute_path_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"inside.py": "x = 1\n"})
    sentinel = tmp_path / "sentinel.py"
    sentinel.write_text("old = True\n")
    patch = _patch(tmp_path, f"--- {sentinel}\n+++ {sentinel}\n@@ -1 +1 @@\n-old = True\n+old = False\n")
    with pytest.raises(PortError, match="not relative"):
        apply_patch(tree, patch)
    assert sentinel.read_text() == "old = True\n"


def test_a_symlink_out_of_the_tree_is_rejected(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"inside.py": "x = 1\n"})
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "f.py").write_text("old = True\n")
    (tree / "link").symlink_to(outside)
    patch = _patch(tmp_path, "--- a/link/f.py\n+++ b/link/f.py\n@@ -1 +1 @@\n-old = True\n+old = False\n")
    with pytest.raises(PortError, match="leads out"):
        apply_patch(tree, patch)
    assert (outside / "f.py").read_text() == "old = True\n"


def test_a_patch_that_fails_on_a_later_file_writes_none_of_its_files(tmp_path: Path) -> None:
    tree = _files(tmp_path, **{"a.py": "x = 1\n", "b.py": "y = 1\n"})
    patch = _patch(tmp_path, (
        "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        "--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-y = 9\n+y = 2\n"
    ))
    with pytest.raises(PortError, match="does not apply"):
        apply_patch(tree, patch)
    assert (tree / "a.py").read_text() == "x = 1\n"


# ---------------------------------------------------------------------------
# Owned paths are synchronized, deletions included
# ---------------------------------------------------------------------------


@pytest.fixture
def smoke_copy(tmp_path: Path) -> tuple[Path, Path]:
    """A throwaway copy of the Known-Best Workspace and of smoke, ported."""
    import shutil

    from scripts.port_from_known_best import port

    known_best = tmp_path / "known_best"
    shutil.copytree(REPO / "known_best", known_best,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    root = tmp_path / "root"
    benchmark = root / "benchmarks/smoke"
    shutil.copytree(REPO / "benchmarks/smoke", benchmark,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    port(benchmark, known_best)
    return known_best, benchmark


def test_a_removed_package_file_disappears_on_the_next_port(smoke_copy) -> None:
    from scripts.port_from_known_best import port

    known_best, benchmark = smoke_copy
    (known_best / "workspace/cards/old_helper.py").write_text("OLD = 1\n")
    port(benchmark, known_best)
    assert (benchmark / "workspace/cards/old_helper.py").is_file()

    (known_best / "workspace/cards/old_helper.py").unlink()
    before = (benchmark / "workspace/cards/old_helper.py").read_text()
    pending = check(benchmark, known_best)
    assert "workspace/cards/old_helper.py" in pending
    assert "data/test_oracle_workspace/cards/old_helper.py" in pending
    assert (benchmark / "workspace/cards/old_helper.py").read_text() == before  # check changed nothing

    port(benchmark, known_best)
    assert not (benchmark / "workspace/cards/old_helper.py").exists()
    assert not (benchmark / "data/test_oracle_workspace/cards/old_helper.py").exists()
    assert check(benchmark, known_best) == []
    # Benchmark-owned paths survive: target cards and the agent documents.
    assert (benchmark / "workspace/cards/fdn/fdn_129/card_spec.json").is_file()
    assert (benchmark / "workspace/AGENTS.md").is_file()


def test_a_removed_workspace_document_disappears_from_the_oracle_mirror(smoke_copy) -> None:
    import shutil

    from scripts.port_from_known_best import port

    known_best, benchmark = smoke_copy
    assert (benchmark / "data/test_oracle_workspace/AGENTS.md").is_file()
    (benchmark / "workspace/AGENTS.md").unlink()
    shutil.rmtree(benchmark / "workspace/skills")
    pending = check(benchmark, known_best)
    assert "data/test_oracle_workspace/AGENTS.md" in pending
    assert "data/test_oracle_workspace/skills" in pending
    port(benchmark, known_best)
    assert not (benchmark / "data/test_oracle_workspace/AGENTS.md").exists()
    assert not (benchmark / "data/test_oracle_workspace/skills").exists()
    assert check(benchmark, known_best) == []


def test_check_on_a_benchmark_with_an_escaping_patch_changes_nothing_outside(smoke_copy) -> None:
    known_best, benchmark = smoke_copy
    sentinel = benchmark.parents[2] / "sentinel.py"
    sentinel.write_text("old = True\n")
    (benchmark / "data/oracle_patches").mkdir(exist_ok=True)
    (benchmark / "data/oracle_patches/zz_escape.patch").write_text(
        f"--- {sentinel}\n+++ {sentinel}\n@@ -1 +1 @@\n-old = True\n+old = False\n"
    )
    with pytest.raises(PortError):
        check(benchmark, known_best)
    assert sentinel.read_text() == "old = True\n"


def _snapshot(tree: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(tree)): path.read_bytes()
        for path in sorted(tree.rglob("*"))
        if path.is_file() and not {"__pycache__", ".pytest_cache"} & set(path.parts)
    }


_STALE = "--- a/engine/__init__.py\n+++ b/engine/__init__.py\n@@ -1 +1 @@\n-this line is nowhere\n+x = 1\n"


def test_a_port_whose_last_defect_patch_no_longer_applies_changes_nothing(smoke_copy) -> None:
    """Earlier steps — copying the Known-Best trees, stubbing targets, the
    earlier patches — are not published when a later patch fails."""
    from scripts.port_from_known_best import port

    known_best, benchmark = smoke_copy
    (known_best / "workspace/engine/__init__.py").write_text(
        (known_best / "workspace/engine/__init__.py").read_text() + "# a Known-Best change\n"
    )
    last = defect_patches(benchmark)[-1]
    last.write_text(_STALE)
    before = _snapshot(benchmark)
    with pytest.raises(PortError, match="does not apply"):
        port(benchmark, known_best)
    assert _snapshot(benchmark) == before


def test_a_port_whose_oracle_patch_no_longer_applies_changes_nothing(smoke_copy) -> None:
    from scripts.port_from_known_best import port

    known_best, benchmark = smoke_copy
    (known_best / "workspace/engine/__init__.py").write_text(
        (known_best / "workspace/engine/__init__.py").read_text() + "# a Known-Best change\n"
    )
    (benchmark / "data/oracle_patches").mkdir(exist_ok=True)
    (benchmark / "data/oracle_patches/zz_stale.patch").write_text(_STALE)
    before = _snapshot(benchmark)
    with pytest.raises(PortError, match="does not apply"):
        port(benchmark, known_best)
    assert _snapshot(benchmark) == before
