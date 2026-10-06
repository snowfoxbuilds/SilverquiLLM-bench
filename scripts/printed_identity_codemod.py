"""Rewrite name-string card identification in tests to predefined classes.

Tests place, choose and assert by predefined classes, never by a name string
(DECISION-MODEL.md › Printed identity; ADR-017). This codemod converts only
the sites that need no inference — a string literal mapped through the
workspace's card registry:

- ``cast_spell(game, i, "Name")`` → ``cast_spell(game, i, Cls)``
- ``declare_attackers(game, ["Name"])`` / ``declare_blockers(game, {"A": ["B"]})``
- ``("name", "Name")`` pairs in a ``GameRef(card=...)`` field → ``("printed", Cls)``
- ``Decision.obj(name="Name")`` / ``Decision.ability(name="Name")`` → ``printed=Cls``
- ``Decision.mode("mode")`` in a card's own suite → ``Decision.mode(printed=Cls)``
  when the card's implementation maps that mode to a predefined class

and adds the imports they need. It never guesses. Every other site carrying
a name is reported for a hand edit, and ``--check`` fails while any report
remains:

- a name pair, a ``Decision`` ``name=`` or a mode whose value is not a string
  literal — a variable, a parameter, an attribute, a computed string;
- a helper argument that is a computed string (an f-string, a concatenation);
- ``obj.name == "Name"`` when the literal names a predefined card and no
  object in the file is built with that name (a test object's own name is a
  characteristic it may assert);
- a literal naming no predefined card (a synthetic test object or a token);
- a literal some object in the file is built with (``name="Name"``), which
  may be the test's own object rather than the printed card;
- in a file it would otherwise convert, an object built with a name that is
  not a literal (``name=label``, ``setdefault("name", label)``), which may
  name the test's own object after a printed card;
- a literal whose class name the file binds to anything other than the
  import of that very class from its own card module;
- a helper or ``Decision`` call whose name the file binds to anything other
  than its import;
- a ``("name", "Name")`` pair naming a predefined card outside a
  ``GameRef(card=...)`` field; any other pair outside one is not a card
  identity and is left alone.

A file is converted whole or not at all: if any site in it needs a hand
edit, the file keeps its original text and every such site is reported.
Helper arguments that are not strings (classes, objects, variables) are left
alone; the helpers themselves reject a string at runtime.

Usage::

    python3 scripts/printed_identity_codemod.py --workspace known_best/workspace \
        [--check] FILE_OR_DIR...
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

HELPER_MODULE = "test_utils"

# Suites whose subject is name-keyed by design, not a test identifying a card.
EXEMPT = {
    "test_registry_loader.py": "the card registry is keyed by printed name",
    "test_decisions.py": "unit tests of the Decision attr schema, whose `name` attr engines still emit",
    "test_refs_registry.py": "unit tests of GameRef fields, whose zone field carries a zone name",
}


@dataclass(frozen=True)
class PrintedRef:
    cls: str
    module: str


@dataclass
class Catalog:
    """Predefined classes of a workspace, keyed by printed name."""

    by_name: dict[str, PrintedRef]
    modes: dict[str, dict[str, PrintedRef]]  # card dir module → mode name → class

    @classmethod
    def load(cls, workspace: Path) -> Catalog:
        sys.path.insert(0, str(workspace))
        from engine.card import GameObject

        by_name: dict[str, PrintedRef] = {}
        clashes: dict[str, set[PrintedRef]] = {}
        modes: dict[str, dict[str, PrintedRef]] = {}

        def record(name: str, ref: PrintedRef) -> None:
            if name in by_name and by_name[name] != ref:
                clashes.setdefault(name, {by_name[name]}).add(ref)
            by_name.setdefault(name, ref)

        for spec_path in sorted(workspace.glob("cards/*/*/card_spec.json")):
            card_dir = spec_path.parent
            module_name = ".".join(card_dir.relative_to(workspace).parts) + ".card_impl"
            spec_name = json.loads(spec_path.read_text())["name"]
            module = importlib.import_module(module_name)
            found = None
            for attr, value in vars(module).items():
                if not (isinstance(value, type) and issubclass(value, GameObject)):
                    continue
                try:
                    instance = value()
                except (TypeError, ValueError):  # needs constructor arguments: not a card
                    continue
                if getattr(instance, "name", None) == spec_name:
                    found = PrintedRef(attr, module_name)
                    break
            if found is None:
                raise SystemExit(f"{module_name}: no class prints as {spec_name!r}")
            record(spec_name, found)
            card_modes = _mode_map(card_dir / "card_impl.py", module_name)
            for mode in getattr(instance, "get_modes", list)() or []:
                printed = getattr(mode, "printed", None)
                if printed is not None and getattr(module, printed.__name__, None) is printed:
                    card_modes[mode.name] = PrintedRef(printed.__name__, module_name)
            modes[module_name] = card_modes

        tokens = importlib.import_module("cards.fdn.tokens")
        for attr, value in vars(tokens).items():
            if isinstance(value, type) and issubclass(value, GameObject) and attr.endswith("Token"):
                record(value().name, PrintedRef(attr, "cards.fdn.tokens"))

        if clashes:
            raise SystemExit(f"ambiguous printed names: {clashes}")
        return cls(by_name, modes)


def _mode_map(impl: Path, module_name: str) -> dict[str, PrintedRef]:
    """Mode name → predefined class, read statically from the implementation:
    ``{'mode': CardAbilityN}`` dicts and ``choose_mode(..., ['a', 'b'], ...,
    printed=[CardAbilityN, CardAbilityM])`` calls."""
    tree = ast.parse(impl.read_text())
    out: dict[str, PrintedRef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "choose_mode":
            names = node.args[2] if len(node.args) > 2 else None
            printed = next((k.value for k in node.keywords if k.arg == "printed"), None)
            if isinstance(names, ast.List) and isinstance(printed, ast.List):
                for key, value in zip(names.elts, printed.elts):
                    if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                        out[key.value] = PrintedRef(value.id, module_name)
            continue
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Name)
                and "Ability" in value.id
            ):
                out[key.value] = PrintedRef(value.id, module_name)
    return out


@dataclass
class Rewrite:
    path: Path
    source: str
    edits: list[tuple[int, int, str]] = field(default_factory=list)
    imports: set[PrintedRef] = field(default_factory=set)
    manual: list[str] = field(default_factory=list)

    def offset(self, line: int, col: int) -> int:
        return self._line_starts[line - 1] + len(
            self.source.splitlines(keepends=True)[line - 1].encode()[:col].decode()
        )

    def __post_init__(self) -> None:
        starts, pos = [], 0
        for text in self.source.splitlines(keepends=True):
            starts.append(pos)
            pos += len(text)
        starts.append(pos)
        self._line_starts = starts

    def replace(self, node: ast.AST, text: str) -> None:
        start = self.offset(node.lineno, node.col_offset)
        end = self.offset(node.end_lineno, node.end_col_offset)
        self.edits.append((start, end, text))

    def segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or ""

    def note(self, node: ast.AST, why: str) -> None:
        self.manual.append(f"{self.path}:{node.lineno}: {why}: {self.segment(node)[:90]}")


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_computed_str(node: ast.AST) -> bool:
    """An f-string, or a concatenation or ``%`` format involving a string."""
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.BinOp) and (
        _is_str(node.left) or _is_str(node.right)
        or _is_computed_str(node.left) or _is_computed_str(node.right)
    )


def _built_names(tree: ast.Module) -> tuple[set[str], list[ast.AST]]:
    """The names objects in the file are built with — ``name=...`` passed to
    a call other than a ``Decision`` constructor, or ``setdefault("name",
    ...)``: the string literals, and the sites whose name is not one."""
    built: set[str] = set()
    unknown: list[ast.AST] = []

    def record(value: ast.AST, site: ast.AST) -> None:
        if _is_str(value):
            built.add(value.value)
        else:
            unknown.append(site)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and getattr(func.value, "id", None) == "Decision":
            continue
        for k in node.keywords:
            if k.arg == "name":
                record(k.value, node)
        if (
            getattr(func, "attr", None) == "setdefault"
            and len(node.args) == 2
            and _is_str(node.args[0])
            and node.args[0].value == "name"
        ):
            record(node.args[1], node)
    return built, unknown


def _bindings(tree: ast.Module) -> dict[str, list[ast.AST]]:
    """Every site in the file, in any scope, that binds each name."""
    bindings: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings.setdefault(node.id, []).append(node)
        elif isinstance(node, ast.arg):
            bindings.setdefault(node.arg, []).append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings.setdefault(node.name, []).append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bindings.setdefault((alias.asname or alias.name).split(".")[0], []).append(node)
        elif isinstance(node, ast.ExceptHandler) and node.name or isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bindings.setdefault(node.name, []).append(node)
    return bindings


class _Visitor(ast.NodeVisitor):
    def __init__(self, rw: Rewrite, catalog: Catalog, tree: ast.Module, own_card: str | None):
        self.rw = rw
        self.catalog = catalog
        self.helpers = _helpers_imported(tree)
        self.own_card = own_card
        self.built, self.unknown_built = _built_names(tree)
        self.bindings = _bindings(tree)

    _in_raises = 0
    _in_card_field = 0

    def _imported_only(self, name: str, module: str | None = None) -> bool:
        """Whether *name* means one import of itself in this file — from
        *module*, when given — and nothing else: no def, assignment,
        parameter or second import rebinds it."""
        sites = self.bindings.get(name, [])
        return len(sites) == 1 and isinstance(sites[0], ast.ImportFrom) and (
            module is None or sites[0].module == module
        ) and any(a.name == name and a.asname in (None, name) for a in sites[0].names)

    def _emit(self, node: ast.AST, literal: ast.Constant, ref: PrintedRef | None, text: str) -> None:
        """Replace *node* by *text* naming *ref*'s class, or report why not."""
        name = literal.value
        if ref is None:
            self.rw.note(node, f"{name!r} names no predefined class here")
        elif name in self.built:
            self.rw.note(node, f"an object in this file is built with the name {name!r}")
        elif not self._names_class(ref):
            self.rw.note(node, f"class {ref.cls} is bound to something else in this file")
        else:
            self.rw.imports.add(ref)
            self.rw.replace(node, text.format(cls=ref.cls))

    def _names_class(self, ref: PrintedRef) -> bool:
        """Whether *ref*'s class name means that class anywhere in the file:
        bound nowhere (the rewrite imports it) or only by its own import."""
        sites = self.bindings.get(ref.cls, [])
        return not sites or (
            len(sites) == 1
            and isinstance(sites[0], ast.ImportFrom)
            and sites[0].module == ref.module
            and any(a.name == ref.cls and a.asname in (None, ref.cls) for a in sites[0].names)
        )

    def _card(self, node: ast.AST) -> None:
        if _is_str(node):
            self._emit(node, node, self.catalog.by_name.get(node.value), "{cls}")
        elif _is_computed_str(node):
            self.rw.note(node, "computed card name")

    def visit_With(self, node: ast.With) -> None:
        # A ``with pytest.raises(...SetupError)`` body tests a helper's own
        # argument checking, so it passes wrong values on purpose.
        raises = any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "attr", None) == "raises"
            and item.context_expr.args
            and "SetupError" in self.rw.segment(item.context_expr.args[0])
            for item in node.items
        )
        self._in_raises += raises
        self.generic_visit(node)
        self._in_raises -= raises

    def visit_Call(self, node: ast.Call) -> None:
        name = node.func.id if isinstance(node.func, ast.Name) else None
        args = node.args
        if name in self.helpers and not self._in_raises and not self._imported_only(name, HELPER_MODULE):
            if any(_is_str(a) and a.value in self.catalog.by_name for a in ast.walk(node)):
                self.rw.note(node, f"{name} is bound to something else in this file")
        elif name in self.helpers and not self._in_raises:
            if name == "cast_spell" and len(args) >= 3:
                self._card(args[2])
            elif name == "declare_attackers" and len(args) >= 2 and isinstance(args[1], (ast.List, ast.Tuple)):
                for elt in args[1].elts:
                    self._card(elt)
            elif name == "declare_blockers" and len(args) >= 2 and isinstance(args[1], ast.Dict):
                for key, value in zip(args[1].keys, args[1].values):
                    if key is not None:
                        self._card(key)
                    if isinstance(value, (ast.List, ast.Tuple)):
                        for elt in value.elts:
                            self._card(elt)
        if isinstance(node.func, ast.Attribute) and getattr(node.func.value, "id", None) == "Decision":
            if self._imported_only("Decision"):
                self._decision(node)
            elif any(k.arg == "name" for k in node.keywords) or (node.func.attr == "mode" and node.args):
                self.rw.note(node, "Decision is bound to something else in this file")
        if getattr(node.func, "id", getattr(node.func, "attr", None)) == "GameRef":
            for child in [node.func, *node.args]:
                self.visit(child)
            for kw in node.keywords:
                card_field = kw.arg == "card"
                self._in_card_field += card_field
                self.visit(kw)
                self._in_card_field -= card_field
            return
        self.generic_visit(node)

    def _decision(self, node: ast.Call) -> None:
        kind = node.func.attr
        for kw in node.keywords:
            if kw.arg != "name":
                continue
            if kind == "mode":
                self._mode(kw.value, whole=kw)
            elif _is_str(kw.value):
                self._emit(kw, kw.value, self.catalog.by_name.get(kw.value.value), "printed={cls}")
            else:
                self.rw.note(node, "Decision name= with a value that is not a literal")
        if kind == "mode" and node.args:
            self._mode(node.args[0], whole=node.args[0])

    def _mode(self, value: ast.AST, whole: ast.AST) -> None:
        if not _is_str(value):
            self.rw.note(value, "Decision.mode with a name that is not a literal")
            return
        ref = self.catalog.modes.get(self.own_card or "", {}).get(value.value)
        self._emit(whole, value, ref, "printed={cls}")

    def visit_Tuple(self, node: ast.Tuple) -> None:
        elts = node.elts
        if len(elts) == 2 and _is_str(elts[0]) and elts[0].value == "name":
            value = elts[1]
            if not self._in_card_field:
                # Not a card identity; report it only when it names a card.
                if _is_str(value) and value.value in self.catalog.by_name:
                    self.rw.note(node, "name pair naming a card outside a GameRef card field")
            elif _is_str(value):
                self._emit(node, value, self.catalog.by_name.get(value.value), '("printed", {cls})')
            else:
                self.rw.note(node, "name pair with a value that is not a literal")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            left, right = node.left, node.comparators[0]
            if isinstance(right, ast.Attribute) and right.attr == "name":
                left, right = right, left
            if (
                isinstance(left, ast.Attribute)
                and left.attr == "name"
                and _is_str(right)
                and right.value in self.catalog.by_name
                and right.value not in self.built
            ):
                self.rw.note(node, "name comparison with a predefined card's name; compare printed_class")
        self.generic_visit(node)


def _helpers_imported(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == HELPER_MODULE:
            names.update(a.asname or a.name for a in node.names)
    return names


def _own_card_module(path: Path) -> str | None:
    """The card module a per-card suite tests (``cards.fdn.fdn_113.card_impl``)."""
    parts = path.parts
    for i, part in enumerate(parts[:-1]):
        if part in {"fdn", "fra", "hob"} and parts[i + 1].startswith(("fdn_", "spg_", "fra_", "hob_")):
            return f"cards.{part}.{parts[i + 1]}.card_impl"
    return None


def _import_edits(rw: Rewrite, tree: ast.Module) -> tuple[list[tuple[int, int, str]], str]:
    """Edits extending existing ``from module import ...`` statements, and the
    text of new import lines for modules not yet imported from."""
    present: set[tuple[str, str]] = set()
    existing: dict[str, ast.ImportFrom] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            present.update((node.module, a.asname or a.name) for a in node.names)
            existing.setdefault(node.module, node)
    wanted: dict[str, set[str]] = {}
    for ref in rw.imports:
        if (ref.module, ref.cls) not in present:
            wanted.setdefault(ref.module, set()).add(ref.cls)
    edits, lines = [], []
    for module in sorted(wanted):
        node = existing.get(module)
        segment = rw.segment(node) if node is not None else ""
        if node is not None and "#" not in segment and node.level == 0:
            names = [f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names]
            names = sorted(set(names) | wanted[module], key=lambda n: (n[:1].islower(), n))
            one_line = f"from {module} import {', '.join(names)}"
            text = one_line if len(one_line) <= 99 else (
                f"from {module} import (\n" + "".join(f"    {n},\n" for n in names) + ")"
            )
            start = rw.offset(node.lineno, node.col_offset)
            end = rw.offset(node.end_lineno, node.end_col_offset)
            edits.append((start, end, text))
        else:
            lines.append(f"from {module} import {', '.join(sorted(wanted[module]))}\n")
    return edits, "".join(lines)


def _insert_at(tree: ast.Module, rw: Rewrite) -> int:
    """Offset just after the last top-level import (or the docstring/future import)."""
    last = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = node
        elif last is not None:
            break
    if last is None:
        return 0
    return rw._line_starts[last.end_lineno]


def rewrite_file(path: Path, catalog: Catalog) -> Rewrite:
    """Rewrite *path* as a whole or not at all: a file with any site that
    needs a hand edit keeps its original text and reports every such site."""
    source = path.read_text()
    rw = Rewrite(path, source)
    if path.name in EXEMPT:
        return rw
    tree = ast.parse(source)
    visitor = _Visitor(rw, catalog, tree, _own_card_module(path))
    visitor.visit(tree)
    if rw.edits:
        for site in visitor.unknown_built:
            rw.note(site, "an object in this file is built with a name that is not a literal")
    if rw.manual or not rw.edits:
        return rw
    text = source
    import_edits, imports = _import_edits(rw, tree)
    edits = sorted(rw.edits + import_edits, reverse=True)
    if imports:
        at = _insert_at(tree, rw)
        edits = sorted(edits + [(at, at, imports)], reverse=True)
    for start, end, new in edits:
        text = text[:start] + new + text[end:]
    rw.source = text
    return rw


def iter_test_files(paths: list[Path]):
    for p in paths:
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*.py") if f.name == "tests.py" or f.name.startswith("test_"))
        else:
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="report only; fail if anything to do")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    catalog = Catalog.load(args.workspace.resolve())
    changed, manual = 0, []
    for path in iter_test_files(args.paths):
        original = path.read_text()
        rw = rewrite_file(path, catalog)
        manual.extend(rw.manual)
        if rw.source != original:
            changed += 1
            if not args.check:
                path.write_text(rw.source)
    for line in manual:
        print(line)
    print(f"{'would change' if args.check else 'changed'} {changed} files; {len(manual)} sites need a hand edit")
    return 1 if (args.check and (changed or manual)) else 0


if __name__ == "__main__":
    sys.exit(main())
