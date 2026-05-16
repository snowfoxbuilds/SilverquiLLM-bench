#!/usr/bin/env python3
"""Bulk-rename power/toughness attribute names for the MTG rules alignment migration.

Renames:
  _original_plus_one_counters  -> _base_plus_one_counters
  _original_minus_one_counters -> _base_minus_one_counters
  .base_power  (attribute access) -> .modified_power
  .base_toughness (attribute access) -> .modified_toughness

Does NOT touch:
  - engine/card.py (already updated manually)
  - constructor kwargs: base_power=N, base_toughness=N
  - kwargs.setdefault("base_power", ...)
  - string literals containing "base_power"
"""
from __future__ import annotations

import os
import re
import sys


def rename_in_content(content: str, *, rename_attr_pt: bool = True) -> str:
    """Apply all renames to file content."""
    # Counter snapshot renames — simple global replace.
    content = content.replace("_original_plus_one_counters", "_base_plus_one_counters")
    content = content.replace("_original_minus_one_counters", "_base_minus_one_counters")

    if rename_attr_pt:
        # Attribute-access renames: match a dot followed by the attribute name.
        # This matches obj.base_power, self.base_power, etc.
        # Does NOT match "base_power" (string literal), base_power= (kwarg name).
        content = re.sub(r'\.base_power\b', '.modified_power', content)
        content = re.sub(r'\.base_toughness\b', '.modified_toughness', content)

    return content


def process_file(filepath: str, *, rename_attr_pt: bool = True, dry_run: bool = False) -> bool:
    """Process a single file. Returns True if the file was modified."""
    with open(filepath, encoding="utf-8") as f:
        original = f.read()

    updated = rename_in_content(original, rename_attr_pt=rename_attr_pt)

    if updated == original:
        return False

    if dry_run:
        print(f"[DRY RUN] Would modify: {filepath}")
        return True

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"Modified: {filepath}")
    return True


def collect_files(roots: list[str], exclude_files: list[str]) -> list[str]:
    files = []
    exclude_set = {os.path.abspath(p) for p in exclude_files}
    for root in roots:
        for dirpath, _dirs, filenames in os.walk(root):
            # Skip __pycache__ and venv
            _dirs[:] = [d for d in _dirs if d not in ("__pycache__", "venv", ".git")]
            for fname in filenames:
                if fname.endswith(".py"):
                    abspath = os.path.abspath(os.path.join(dirpath, fname))
                    if abspath not in exclude_set:
                        files.append(abspath)
    return files


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dry_run = "--dry-run" in sys.argv

    # engine/card.py already updated in Phase 1 — exclude it.
    exclude = [os.path.join(repo_root, "engine", "card.py")]

    # Cards directory: rename both counter attrs AND .base_power/.base_toughness.
    card_roots = [
        os.path.join(repo_root, "cards"),
    ]

    # Engine files (except card.py): only counter renames, NOT .base_power
    # (combat.py uses hasattr(c, "base_power") as a creature check — still valid
    #  since Creature.base_power = printed value still exists).
    engine_roots = [os.path.join(repo_root, "engine")]

    # Test files: rename counters AND .base_power in effect-context files.
    # test_card.py checks base_power right after construction (printed value) — skip PT rename there.
    test_pt_files = [
        os.path.join(repo_root, "tests", "engine", "test_continuous_effects.py"),
        os.path.join(repo_root, "tests", "engine", "test_cleanup.py"),
        os.path.join(repo_root, "tests", "engine", "test_protection.py"),
        os.path.join(repo_root, "tests", "engine", "test_lazy_targets.py"),
    ]
    # Audited FDN tests: only counter renames (base_power checks are printed-value checks).
    audited_roots = [os.path.join(repo_root, "tests", "audited")]

    modified = 0

    print("=== Cards directory (PT rename + counter rename) ===")
    for f in collect_files(card_roots, exclude):
        if process_file(f, rename_attr_pt=True, dry_run=dry_run):
            modified += 1

    print("\n=== Engine directory (counter rename only) ===")
    for f in collect_files(engine_roots, exclude):
        if process_file(f, rename_attr_pt=False, dry_run=dry_run):
            modified += 1

    print("\n=== Test effect files (PT rename + counter rename) ===")
    for f in test_pt_files:
        if os.path.exists(f):
            if process_file(f, rename_attr_pt=True, dry_run=dry_run):
                modified += 1

    print("\n=== Audited test directory (counter rename only) ===")
    for f in collect_files(audited_roots, exclude):
        if process_file(f, rename_attr_pt=False, dry_run=dry_run):
            modified += 1

    print(f"\nTotal files modified: {modified}")


if __name__ == "__main__":
    main()
