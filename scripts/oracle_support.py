"""Benchmark-aware oracle paths, readiness checks and V2 audit conformance."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OracleLayout:
    root: Path
    benchmark: str
    target_set: str
    cards: tuple[str, ...]

    @property
    def benchmark_root(self) -> Path:
        return self.root / "benchmarks" / self.benchmark

    @property
    def workspace(self) -> Path:
        return self.benchmark_root / "workspace"

    @property
    def oracle(self) -> Path:
        return self.benchmark_root / "data/test_oracle_workspace"

    @property
    def audited(self) -> Path:
        return self.benchmark_root / "data/tests/audited" / self.target_set

    def implementation(self, card: str) -> Path:
        return self.oracle / "cards" / self.target_set / card / "card_impl.py"

    def suite(self, card: str) -> Path:
        return self.audited / card / "tests.py"


def load_layout(root: Path, benchmark: str, *, require_cards: bool = False) -> OracleLayout:
    data = json.loads((root / "benchmarks" / benchmark / "config.json").read_text())
    target = data.get("draft_set", {}).get("primary_set_code", benchmark).lower()
    cards = tuple(f"{target}_{str(number).lstrip('0') or '0'}" for number in data.get("cards", ()))
    if require_cards and not cards:
        raise ValueError(f"{benchmark}: no selected cards in config.json")
    return OracleLayout(root, benchmark, target, cards)


def is_stub_impl(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return True
    return not any(
        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not member.name.startswith("__")
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for member in node.body
    )


def readiness_errors(layout: OracleLayout, card: str) -> list[str]:
    errors = []
    impl, suite = layout.implementation(card), layout.suite(card)
    if not impl.is_file():
        errors.append(f"missing oracle implementation: {impl}")
    elif is_stub_impl(impl):
        errors.append(f"stub or invalid oracle implementation: {impl}")
    if not suite.is_file():
        errors.append(f"missing audited suite: {suite}")
    else:
        try:
            tree = ast.parse(suite.read_text())
        except (OSError, SyntaxError) as error:
            errors.append(f"invalid audited suite {suite}: {error}")
        else:
            if not any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test_")
                for n in ast.walk(tree)
            ):
                errors.append(f"empty audited suite: {suite}")
    return errors


_DIRECT_HOOKS = frozenset(
    {
        "on_cast",
        "on_resolve",
        "as_enters",
        "prepare_cast",
        "can_cast",
        "get_targets",
        "register_triggers",
        "register_replacement_effects",
        "get_activated_abilities",
        "get_loyalty_abilities",
        "get_mana_abilities",
        "get_modes",
        "cost_reduction",
        "apply_continuous_effect",
        "on_enchant",
        "on_detach",
        "effect",
        "cost",
        "mana_produced",
        "fire_event",
        "register",
        "unregister",
    }
)
_CARD_BASES = frozenset(
    {
        "CardImpl",
        "Creature",
        "Instant",
        "Sorcery",
        "Enchantment",
        "Aura",
        "Artifact",
        "ArtifactCreature",
        "Land",
        "Equipment",
        "Planeswalker",
    }
)


def public_symbols(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text())
    result = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            result.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            result.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            result.add(node.target.id)
    return result


def check_v2_api(path: Path, layout: OracleLayout, *, helper: bool = False) -> list[str]:
    """Check canonical imports and aliased private/hook access without V1 directives."""
    tree = ast.parse(path.read_text())
    issues = []
    aliases: dict[str, str] = {}
    helper_symbols = public_symbols(layout.oracle / "test_utils.py")

    def report(node: ast.AST, message: str) -> None:
        issues.append(f"{path}:{node.lineno}: {message}")

    def validate_import(node: ast.AST, module: str, name: str | None = None) -> None:
        if module == "test_utils" and name is not None:
            if name.startswith("_") or name not in helper_symbols:
                report(node, f"unknown/private host helper: {name}")
            return
        if module != "engine" and not module.startswith("engine."):
            return
        relative = Path(*module.split("."))
        source = layout.workspace / relative.with_suffix(".py")
        if not source.is_file():
            source = layout.workspace / relative / "__init__.py"
        if not source.is_file():
            report(node, f"oracle-only or unknown engine module: {module}")
        elif name is not None:
            child = layout.workspace / relative / f"{name}.py"
            if name not in public_symbols(source) and not child.is_file():
                report(node, f"oracle-only or unknown canonical symbol: {module}.{name}")
            elif name.startswith("_") and not helper:
                report(node, f"private engine import: {module}.{name}")

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
                validate_import(node, node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
                validate_import(node, alias.name)

    def qualified(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        if (
            isinstance(node, ast.Call)
            and qualified(node.func).split(".")[-1] == "getattr"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
        ):
            return f"{qualified(node.args[0])}.{node.args[1].value}"
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = qualified(node.value)
            if value:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases[target.id] = value

    fixture_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            qualified(base).split(".")[-1] in _CARD_BASES for base in node.bases
        ):
            fixture_nodes.update(id(child) for child in ast.walk(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            owner = qualified(node.value)
            module_path = layout.workspace / Path(*owner.split("."))
            if (owner == "engine" or owner.startswith("engine.")) and (
                module_path.with_suffix(".py").is_file() or (module_path / "__init__.py").is_file()
            ):
                validate_import(node, owner, node.attr)
        if helper or id(node) in fixture_nodes:
            continue
        if isinstance(node, ast.Attribute):
            on_self = isinstance(node.value, ast.Name) and node.value.id == "self"
            if node.attr.startswith("_") and node.attr != "__init__" and not on_self:
                report(node, f"private attribute: {node.attr}")
        if isinstance(node, ast.Call):
            name = qualified(node.func).split(".")[-1]
            if name in _DIRECT_HOOKS:
                report(node, f"direct card/ability hook: {name}")
            if name in {"getattr", "setattr", "hasattr"} and len(node.args) > 1:
                member = node.args[1]
                if (
                    isinstance(member, ast.Constant)
                    and isinstance(member.value, str)
                    and (member.value.startswith("_") or member.value in _DIRECT_HOOKS)
                ):
                    report(node, f"dynamic private/hook access: {member.value}")
    return sorted(set(issues))
