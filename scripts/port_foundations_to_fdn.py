#!/usr/bin/env python3
"""Port implemented card classes from cards/foundations/ to cards/fdn/.

Scans all cards/foundations/*.py files, extracts card class definitions,
matches them against cards/fdn/*/card_spec.json by card name, and
rewrites the corresponding card_impl.py stubs with real implementations.

Two modes:
  --import-mode   (default) Each card_impl.py imports from foundations and
                  re-exports. Minimal diff, no code duplication.
  --inline-mode   Each card_impl.py gets a self-contained copy of the class
                  with all necessary imports and helpers inlined.

Usage:
    python port_foundations_to_fdn.py [--dry-run] [--inline-mode] [--verbose]

Run from the repo root (SilverquiLLM-bench/).
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path.cwd()
FDN_DIR = REPO_ROOT / "cards" / "fdn"
FOUNDATIONS_DIR = REPO_ROOT / "cards" / "foundations"

# Basic lands are handled by the engine, not foundations files
BASIC_LAND_DIRS = {"272", "274", "276", "278", "280"}

# Set of foundations files that should NOT be touched even if empty
# (e.g. shared utility modules)
PROTECTED_FILES: set[str] = set()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FoundationsClass:
    """A card class found in a foundations module."""
    card_name: str              # e.g. "Healer's Hawk"
    class_name: str             # e.g. "HealersHawk"
    module_file: str            # e.g. "simple_creatures"
    module_path: str            # e.g. "cards.foundations.simple_creatures"
    is_factory: bool = False    # True if created via make_vanilla etc.
    base_class: str = ""        # e.g. "Creature", "Instant"


@dataclass
class FdnStub:
    """A stub card_impl.py in cards/fdn/."""
    dir_name: str               # e.g. "142" or "spg_74"
    card_name: str              # from card_spec.json
    stub_class_name: str        # from card_impl.py, e.g. "HealersHawk"
    spec_path: Path
    impl_path: Path


# ---------------------------------------------------------------------------
# Card name → class name normalization
# ---------------------------------------------------------------------------

def card_name_to_class_name(name: str) -> str:
    """Convert a card name to its expected PascalCase class name.

    Mirrors the convention used in the stub generator:
      "Healer's Hawk"           -> "HealersHawk"
      "Ajani, Caller of the Pride" -> "AjaniCallerOfThePride"
      "An Offer You Can't Refuse"  -> "AnOfferYouCantRefuse"
    """
    # Remove apostrophes, commas, hyphens, colons
    cleaned = name.replace("'", "").replace(",", "").replace("-", " ")
    cleaned = cleaned.replace(":", "")
    # Title-case each word and join
    return "".join(word.capitalize() for word in cleaned.split())


def normalize_card_name(name: str) -> str:
    """Lowercase, strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ---------------------------------------------------------------------------
# Step 1: Scan foundations files for class definitions
# ---------------------------------------------------------------------------

def extract_classes_from_foundations() -> dict[str, FoundationsClass]:
    """Parse all cards/foundations/*.py and return card_name -> FoundationsClass.

    Uses two strategies:
    1. AST: Find class definitions with kwargs.setdefault("name", <card_name>)
    2. AST: Find top-level assignments like `X = make_vanilla("Card Name", ...)`
    3. Registration lists: Parse _ALL_* tuples for (name, class, ...) patterns
    """
    result: dict[str, FoundationsClass] = {}  # normalized_name -> FoundationsClass

    if not FOUNDATIONS_DIR.exists():
        print(f"ERROR: {FOUNDATIONS_DIR} not found. Run from repo root.", file=sys.stderr)
        sys.exit(1)

    for py_file in sorted(FOUNDATIONS_DIR.glob("*.py")):
        if py_file.name.startswith("__"):
            continue

        module_name = py_file.stem  # e.g. "simple_creatures"
        module_path = f"cards.foundations.{module_name}"

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            print(f"  WARN: Syntax error in {py_file}: {e}", file=sys.stderr)
            continue

        # --- Strategy 1: Class definitions ---
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                card_name = _extract_name_from_class(node, source)
                if card_name:
                    base = _get_base_class(node)
                    key = normalize_card_name(card_name)
                    result[key] = FoundationsClass(
                        card_name=card_name,
                        class_name=node.name,
                        module_file=module_name,
                        module_path=module_path,
                        is_factory=False,
                        base_class=base,
                    )

        # --- Strategy 2: Factory assignments like X = make_vanilla(...) ---
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                    func = node.value
                    func_name = _get_call_name(func)
                    if func_name and "make_" in func_name and func.args:
                        first_arg = func.args[0]
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            card_name = first_arg.value
                            key = normalize_card_name(card_name)
                            result[key] = FoundationsClass(
                                card_name=card_name,
                                class_name=target.id,
                                module_file=module_name,
                                module_path=module_path,
                                is_factory=True,
                                base_class="Creature",
                            )

    return result


def _extract_name_from_class(cls_node: ast.ClassDef, source: str) -> str | None:
    """Extract the card name from a class's __init__ method.

    Looks for: kwargs.setdefault("name", "Card Name")
    """
    for node in ast.walk(cls_node):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "setdefault"
                and len(node.args) >= 2
            ):
                first_arg = node.args[0]
                second_arg = node.args[1]
                if (
                    isinstance(first_arg, ast.Constant)
                    and first_arg.value == "name"
                    and isinstance(second_arg, ast.Constant)
                    and isinstance(second_arg.value, str)
                ):
                    return second_arg.value
    return None


def _get_base_class(cls_node: ast.ClassDef) -> str:
    """Get the first base class name of a class definition."""
    if cls_node.bases:
        base = cls_node.bases[0]
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
    return ""


def _get_call_name(call: ast.Call) -> str | None:
    """Get the function name from a Call node."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    elif isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


# ---------------------------------------------------------------------------
# Step 2: Scan fdn directories for stubs
# ---------------------------------------------------------------------------

def scan_fdn_stubs() -> list[FdnStub]:
    """Scan cards/fdn/*/card_spec.json and card_impl.py for stubs."""
    stubs: list[FdnStub] = []

    if not FDN_DIR.exists():
        print(f"ERROR: {FDN_DIR} not found. Run from repo root.", file=sys.stderr)
        sys.exit(1)

    for entry in sorted(FDN_DIR.iterdir()):
        if not entry.is_dir():
            continue

        dir_name = entry.name
        spec_path = entry / "card_spec.json"
        impl_path = entry / "card_impl.py"

        if not spec_path.exists() or not impl_path.exists():
            continue

        # Skip basic lands (handled by engine)
        if dir_name in BASIC_LAND_DIRS:
            continue

        # Read card name from spec
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            card_name = spec["name"]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARN: Bad card_spec.json in {dir_name}: {e}", file=sys.stderr)
            continue

        # Read stub class name from impl
        stub_class_name = _extract_stub_class_name(impl_path)
        if not stub_class_name:
            print(f"  WARN: No class found in {impl_path}", file=sys.stderr)
            continue

        stubs.append(FdnStub(
            dir_name=dir_name,
            card_name=card_name,
            stub_class_name=stub_class_name,
            spec_path=spec_path,
            impl_path=impl_path,
        ))

    return stubs


def _extract_stub_class_name(impl_path: Path) -> str | None:
    """Extract the class name from a card_impl.py stub."""
    try:
        source = impl_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                return node.name
    except SyntaxError:
        pass
    return None


def _is_todo_stub(impl_path: Path) -> bool:
    """Check if a card_impl.py is still a TODO stub."""
    source = impl_path.read_text(encoding="utf-8")
    return "TODO:" in source and "\n    pass\n" in source


# ---------------------------------------------------------------------------
# Step 3: Generate new card_impl.py content
# ---------------------------------------------------------------------------

def generate_import_mode(stub: FdnStub, fclass: FoundationsClass) -> str:
    """Generate a card_impl.py that imports from foundations.

    This is the thin-wrapper approach: minimal code, no duplication.
    The class is imported and aliased to the stub's expected name.
    """
    lines = [
        f'"""Card implementation for {stub.card_name}."""',
        "",
    ]

    # If the class names match, a simple import suffices
    if fclass.class_name == stub.stub_class_name:
        lines.append(
            f"from {fclass.module_path} import {fclass.class_name}"
        )
    else:
        # Alias import to match the stub's expected class name
        lines.append(
            f"from {fclass.module_path} import {fclass.class_name} "
            f"as {stub.stub_class_name}"
        )

    lines.append("")
    return "\n".join(lines)


def generate_inline_mode(stub: FdnStub, fclass: FoundationsClass) -> str:
    """Generate a self-contained card_impl.py with the class code inlined.

    Reads the source file, extracts the class and its dependencies,
    and produces a standalone module.
    """
    source_path = FOUNDATIONS_DIR / f"{fclass.module_file}.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the class or assignment node
    class_source = _extract_node_source(source, tree, fclass)
    if class_source is None:
        # Fallback to import mode
        return generate_import_mode(stub, fclass)

    # Collect imports from the source file
    imports = _extract_imports(source, tree)

    # Collect helper functions referenced by the class
    helpers = _extract_helpers(source, tree, fclass)

    lines = [
        f'"""Card implementation for {stub.card_name}."""',
        "",
        *imports,
        "",
    ]

    if helpers:
        lines.extend(helpers)
        lines.append("")

    lines.append(class_source)

    # If class name doesn't match stub, add an alias
    if fclass.class_name != stub.stub_class_name:
        lines.append("")
        lines.append(f"{stub.stub_class_name} = {fclass.class_name}")

    lines.append("")
    return "\n".join(lines)


def _extract_imports(source: str, tree: ast.Module) -> list[str]:
    """Extract all import statements from a module."""
    lines = source.splitlines()
    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Get the source lines for this node
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            import_text = "\n".join(lines[start:end])
            imports.append(import_text)
        elif isinstance(node, ast.If):
            # Handle TYPE_CHECKING blocks
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno)
                import_text = "\n".join(lines[start:end])
                imports.append(import_text)
    return imports


def _extract_node_source(source: str, tree: ast.Module, fclass: FoundationsClass) -> str | None:
    """Extract the source code for a class definition or factory assignment."""
    lines = source.splitlines()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == fclass.class_name:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            # Include any decorators
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            return "\n".join(lines[start:end])

        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == fclass.class_name
        ):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[start:end])

    return None


def _extract_helpers(source: str, tree: ast.Module, fclass: FoundationsClass) -> list[str]:
    """Extract helper functions that the class depends on.

    Simple heuristic: include private functions (starting with _) that are
    referenced in the class source code.
    """
    lines = source.splitlines()
    class_source = _extract_node_source(source, tree, fclass) or ""

    helpers: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
            if node.name in class_source:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno)
                helpers.append("\n".join(lines[start:end]))

    # Also grab make_vanilla if it's a factory class
    if fclass.is_factory:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "make_vanilla":
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno)
                helpers.insert(0, "\n".join(lines[start:end]))
                break

    return helpers


# ---------------------------------------------------------------------------
# Step 4: Main orchestration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step 5: Delete original implementations from foundations
# ---------------------------------------------------------------------------

def delete_originals_from_foundations(
    ported: list[tuple[FdnStub, FoundationsClass]],
    dry_run: bool,
    verbose: bool,
) -> int:
    """Remove ported class/assignment definitions from their foundations source files.

    After removal, if a foundations file contains no remaining class definitions
    or factory assignments (only imports / helpers / empty lines), the entire
    file is deleted.

    Returns the number of source files modified or deleted.
    """
    # Group ported classes by their source module file
    by_module: dict[str, list[FoundationsClass]] = {}
    for _stub, fclass in ported:
        by_module.setdefault(fclass.module_file, []).append(fclass)

    files_modified = 0
    files_deleted = 0

    for module_name, classes in sorted(by_module.items()):
        source_path = FOUNDATIONS_DIR / f"{module_name}.py"
        if not source_path.exists():
            continue

        source = source_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            print(f"  WARN: Cannot parse {source_path}, skipping cleanup", file=sys.stderr)
            continue

        lines = source.splitlines(keepends=True)
        class_names_to_remove = {fc.class_name for fc in classes}

        # Collect line ranges to remove (0-indexed, inclusive)
        ranges_to_remove: list[tuple[int, int]] = []

        for node in ast.iter_child_nodes(tree):
            # Regular class definitions
            if isinstance(node, ast.ClassDef) and node.name in class_names_to_remove:
                start = node.lineno - 1
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                end = getattr(node, "end_lineno", node.lineno) - 1
                ranges_to_remove.append((start, end))

            # Factory assignments: ClassName = make_vanilla(...)
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in class_names_to_remove
            ):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno) - 1
                ranges_to_remove.append((start, end))

        if not ranges_to_remove:
            if verbose:
                print(f"  SKIP {module_name}.py  (no matching nodes found)")
            continue

        # Sort descending so we can remove from bottom to top
        ranges_to_remove.sort(key=lambda r: r[0], reverse=True)

        new_lines = list(lines)
        for start, end in ranges_to_remove:
            # Also remove any blank lines immediately after the removed block
            trailing = end + 1
            while trailing < len(new_lines) and new_lines[trailing].strip() == "":
                trailing += 1
            del new_lines[start:trailing]

        new_source = "".join(new_lines)

        # Check if any card classes or factory assignments remain
        remaining_has_cards = _file_has_remaining_cards(new_source, class_names_to_remove)

        if not remaining_has_cards and module_name not in PROTECTED_FILES:
            # File is now empty of card classes — delete it entirely
            if dry_run:
                print(f"  DELETE {source_path.relative_to(REPO_ROOT)}  "
                      f"(all {len(classes)} classes removed)")
            else:
                source_path.unlink()
                if verbose:
                    print(f"  DELETED {source_path}")
            files_deleted += 1
        else:
            # File still has other cards — rewrite with removed classes
            if dry_run:
                print(f"  CLEAN  {source_path.relative_to(REPO_ROOT)}  "
                      f"(remove {len(ranges_to_remove)} definitions, "
                      f"{'has' if remaining_has_cards else 'no'} remaining cards)")
                if verbose:
                    # Show which classes are removed
                    for fc in classes:
                        print(f"         - {fc.class_name}")
            else:
                source_path.write_text(new_source, encoding="utf-8")
                if verbose:
                    print(f"  WROTE  {source_path}  "
                          f"(removed {len(ranges_to_remove)} definitions)")
            files_modified += 1

    return files_modified + files_deleted


def _file_has_remaining_cards(source: str, excluded: set[str]) -> bool:
    """Check if a source string still contains card class defs or factory assignments
    beyond the ones we just removed."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True  # Be safe: assume it still has content

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name not in excluded:
            # Check if it looks like a card class (has kwargs.setdefault("name", ...))
            if _extract_name_from_class(node, source):
                return True
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id not in excluded
            and isinstance(node.value, ast.Call)
        ):
            func_name = _get_call_name(node.value)
            if func_name and "make_" in func_name:
                return True
    return False


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    inline_mode = "--inline-mode" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    delete_originals = "--delete-originals" in sys.argv

    mode_label = "inline" if inline_mode else "import"
    print(f"=== port_foundations_to_fdn.py ===")
    print(f"Mode: {mode_label}{'  (DRY RUN)' if dry_run else ''}")
    if delete_originals:
        print(f"  --delete-originals: will clean up foundations source files")
    print(f"Repo root: {REPO_ROOT}")
    print()

    # 1. Scan foundations
    print("[1/4] Scanning cards/foundations/ for implementations...")
    fdn_classes = extract_classes_from_foundations()
    print(f"  Found {len(fdn_classes)} card classes")
    if verbose:
        for key, fc in sorted(fdn_classes.items()):
            tag = "(factory)" if fc.is_factory else ""
            print(f"    {fc.card_name:40s} -> {fc.module_file}.{fc.class_name} {tag}")
    print()

    # 2. Scan fdn stubs
    print("[2/4] Scanning cards/fdn/ for stubs...")
    stubs = scan_fdn_stubs()
    print(f"  Found {len(stubs)} card stubs")
    print()

    # 3. Match and generate
    print("[3/4] Matching stubs to implementations...")
    matched = 0
    skipped_already_impl = 0
    skipped_no_match = 0
    errors = 0

    results: list[tuple[FdnStub, FoundationsClass]] = []

    for stub in stubs:
        key = normalize_card_name(stub.card_name)
        fclass = fdn_classes.get(key)

        if fclass is None:
            skipped_no_match += 1
            if verbose:
                print(f"  SKIP {stub.dir_name:>7s}  {stub.card_name:40s}  (no implementation)")
            continue

        if not _is_todo_stub(stub.impl_path):
            skipped_already_impl += 1
            if verbose:
                print(f"  SKIP {stub.dir_name:>7s}  {stub.card_name:40s}  (already implemented)")
            continue

        results.append((stub, fclass))
        matched += 1
        print(f"  PORT {stub.dir_name:>7s}  {stub.card_name:40s}  <- {fclass.module_file}.{fclass.class_name}")

    print()
    print(f"  Matched:              {matched}")
    print(f"  No implementation:    {skipped_no_match}")
    print(f"  Already implemented:  {skipped_already_impl}")
    print()

    # 4. Write files
    print(f"[4/4] {'Would write' if dry_run else 'Writing'} {len(results)} files...")

    for stub, fclass in results:
        try:
            if inline_mode:
                content = generate_inline_mode(stub, fclass)
            else:
                content = generate_import_mode(stub, fclass)

            if dry_run:
                if verbose:
                    print(f"\n--- {stub.impl_path} ---")
                    print(content)
                    print("--- end ---")
            else:
                stub.impl_path.write_text(content, encoding="utf-8")
                if verbose:
                    print(f"  WROTE {stub.impl_path}")

        except Exception as e:
            errors += 1
            print(f"  ERROR {stub.dir_name}: {e}", file=sys.stderr)

    # 5. Delete originals if requested
    if delete_originals and results:
        print()
        successfully_ported = [(s, f) for (s, f) in results
                               if dry_run or s.impl_path.exists()]
        print(f"[5/5] {'Would clean' if dry_run else 'Cleaning'} "
              f"foundations source files ({len(successfully_ported)} classes)...")
        touched = delete_originals_from_foundations(successfully_ported, dry_run, verbose)
        print(f"  Foundations files modified/deleted: {touched}")

    print()
    if dry_run:
        print(f"DRY RUN complete. {matched} files would be written. "
              f"Run without --dry-run to apply.")
    else:
        print(f"Done! {matched - errors} files written, {errors} errors.")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()