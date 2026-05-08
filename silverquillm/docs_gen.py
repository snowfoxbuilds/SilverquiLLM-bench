"""Engine API docs auto-generation.

Parses engine source files with ``ast`` and produces a compact Markdown
reference suitable for agent consumption.  The output is kept under
~5 000 tokens so that it fits comfortably in an LLM context window.

Public API:
- ``generate_engine_api_doc`` — returns Markdown string.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

__all__ = ["generate_engine_api_doc"]

# Budget: approximate token count via ``len(text.split()) * 1.3``.
_TOKEN_BUDGET = 5000
_TRIM_DOCSTRINGS = False  # set dynamically if over budget


def _estimate_tokens(text: str) -> float:
    return len(text.split()) * 1.3


def _format_sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return ``name(arg1, arg2, ...) -> ret`` signature string."""
    args = node.args
    parts: list[str] = []
    # positional args
    for a in args.args:
        name = a.arg
        if name == "self":
            continue
        ann = ""
        if a.annotation:
            ann = f": {ast.unparse(a.annotation)}"
        parts.append(f"{name}{ann}")
    # *args
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    # **kwargs
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    sig = f"{node.name}({', '.join(parts)})"
    if node.returns:
        sig += f" -> {ast.unparse(node.returns)}"
    return sig


def _first_line_docstring(node: ast.AST) -> str:
    """Return first line of docstring, or empty string."""
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    return doc.split("\n")[0].strip()


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _is_enum(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = ""
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        if name in ("Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"):
            return True
    return False


def _is_dataclass(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "dataclass":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
            return True
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "dataclass":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "dataclass":
                return True
    return False


def _enum_members(node: ast.ClassDef) -> list[str]:
    members: list[str] = []
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and _is_public(target.id):
                    members.append(target.id)
    return members


def _dataclass_fields(node: ast.ClassDef) -> list[str]:
    fields: list[str] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            name = item.target.id
            if _is_public(name):
                ann = ast.unparse(item.annotation) if item.annotation else ""
                fields.append(f"{name}: {ann}" if ann else name)
    return fields


def _public_methods(node: ast.ClassDef) -> list[str]:
    sigs: list[str] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_public(item.name):
                sigs.append(_format_sig(item))
    return sigs


def _process_module(filepath: str, trim_docs: bool) -> str:
    """Parse a single .py file and return its Markdown section."""
    with open(filepath) as f:
        source = f.read()
    tree = ast.parse(source, filename=filepath)
    module_name = Path(filepath).stem

    sections: list[str] = []
    # Collect top-level classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            doc = "" if trim_docs else _first_line_docstring(node)
            if _is_enum(node):
                members = _enum_members(node)
                header = f"- **enum `{node.name}`**"
                if doc:
                    header += f" — {doc}"
                if members:
                    header += f"  \n  Members: `{'`, `'.join(members)}`"
                sections.append(header)
            elif _is_dataclass(node):
                fields = _dataclass_fields(node)
                header = f"- **dataclass `{node.name}`**"
                if doc:
                    header += f" — {doc}"
                if fields:
                    header += f"  \n  Fields: `{'`, `'.join(fields)}`"
                sections.append(header)
            else:
                # Regular class
                header = f"- **class `{node.name}`**"
                if doc:
                    header += f" — {doc}"
                methods = _public_methods(node)
                if methods:
                    method_lines = "  \n".join(
                        f"  - `{m}`" for m in methods
                    )
                    header += f"  \n{method_lines}"
                sections.append(header)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_public(node.name):
                continue
            sig = _format_sig(node)
            doc = "" if trim_docs else _first_line_docstring(node)
            entry = f"- `{sig}`"
            if doc:
                entry += f" — {doc}"
            sections.append(entry)

    if not sections:
        return ""
    return f"### {module_name}\n\n" + "\n".join(sections)





def generate_engine_api_doc(engine_dir: str = "engine") -> str:
    """Generate Markdown API reference from engine source files.

    Parameters
    ----------
    engine_dir:
        Path to the engine directory.  Defaults to ``"engine"`` relative
        to the repository root (resolved from this file's location).

    Returns
    -------
    str
        Markdown document describing the public engine API.
    """
    # Resolve relative to this file's directory (repo root / benchmark/)
    base = Path(__file__).resolve().parent.parent
    engine_path = base / engine_dir

    py_files = sorted(
        str(engine_path / f)
        for f in os.listdir(engine_path)
        if f.endswith(".py") and f != "__init__.py"
    )

    # First pass: generate without trimming
    module_sections: list[str] = []
    for fp in py_files:
        section = _process_module(fp, trim_docs=False)
        if section:
            module_sections.append(section)

    doc = _build_doc(module_sections)
    if _estimate_tokens(doc) <= _TOKEN_BUDGET:
        return doc

    # Over budget: regenerate with trimmed docstrings
    module_sections = []
    for fp in py_files:
        section = _process_module(fp, trim_docs=True)
        if section:
            module_sections.append(section)

    return _build_doc(module_sections)


def _build_doc(module_sections: list[str]) -> str:
    header = "# Engine API Reference\n\nAuto-generated from engine source. For agent consumption.\n"
    body = "\n## Modules\n\n" + "\n\n".join(module_sections) + "\n"
    return header + body
