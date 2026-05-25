"""AST migration script: replace EventType enum + dict-based events with typed event objects.

Run from the project root:
    python migrate_events.py

Transforms applied to every .py file under cards/ and tests/:

1. TriggerRegistration(event_type=EventType.X, ...) -> event_type=XTriggeredEvent
2. fire_event(game, EventType.X, {k: v}) -> fire_event(game, XTriggeredEvent(k=v))
3. ReplacementEffect(event_type="x", ...) -> event_type=XReplacementEvent
4. Condition/replacement callable bodies: param rename + dict access -> attribute access
5. Import updates: add engine.events imports, drop EventType from benchmarks.sos.workspace.engine.triggers
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

EVENTTYPE_TO_CLASS: dict[str, str] = {
    "ENTERS_BATTLEFIELD": "EntersBattlefieldTriggeredEvent",
    "LEAVES_BATTLEFIELD": "LeavesBattlefieldTriggeredEvent",
    "DEALS_DAMAGE": "DealsDamageTriggeredEvent",
    "LOSES_LIFE": "LosesLifeTriggeredEvent",
    "GAINS_LIFE": "GainsLifeTriggeredEvent",
    "DRAWS_CARD": "DrawsCardTriggeredEvent",
    "BEGINNING_OF_UPKEEP": "BeginningOfUpkeepTriggeredEvent",
    "BEGINNING_OF_COMBAT": "BeginningOfCombatTriggeredEvent",
    "END_OF_TURN": "EndOfTurnTriggeredEvent",
    "END_STEP": "EndStepTriggeredEvent",
    "CREATURE_DIES": "CreatureDiesTriggeredEvent",
    "SPELL_CAST": "SpellCastTriggeredEvent",
    "ATTACKS": "AttacksTriggeredEvent",
    "BLOCKS": "BlocksTriggeredEvent",
    "COUNTER_ADDED": "CounterAddedTriggeredEvent",
}

STRING_TO_REPLACEMENT_CLASS: dict[str, str] = {
    "creature_dies": "CreatureDiesReplacementEvent",
    "sacrifice": "SacrificeReplacementEvent",
    "permanent_destroyed": "PermanentDestroyedReplacementEvent",
    "move_to_graveyard": "MoveToGraveyardReplacementEvent",
    "create_token": "CreateTokenReplacementEvent",
    "add_counter": "AddCounterReplacementEvent",
}

ALL_EVENT_CLASSES = set(EVENTTYPE_TO_CLASS.values()) | set(STRING_TO_REPLACEMENT_CLASS.values())

# Parameter names that identify an event-data argument in condition/replacement callables.
EVENT_PARAM_NAMES = {"data", "event_data"}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _name(id_: str) -> ast.Name:
    return ast.Name(id=id_, ctx=ast.Load())


def _dict_to_kwargs(dict_node: ast.Dict) -> list[ast.keyword]:
    """Convert a dict literal to keyword args. Only works for string keys."""
    kwargs = []
    for key, val in zip(dict_node.keys, dict_node.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            kwargs.append(ast.keyword(arg=key.value, value=val))
    return kwargs


def _is_eventtype_attr(node: ast.expr) -> str | None:
    """Return the EventType member name if node is EventType.MEMBER, else None."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"EventType", "_ET"}
    ):
        return node.attr
    return None


# ---------------------------------------------------------------------------
# Body transformer: dict access -> attribute access
# ---------------------------------------------------------------------------

class _BodyTransformer(ast.NodeTransformer):
    """Replaces dict access on a named event-data parameter with attribute access."""

    def __init__(self, param_name: str) -> None:
        self.param_name = param_name

    def _is_param(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Name) and node.id == self.param_name

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        # Check pattern BEFORE generic_visit renames the param.
        # param["key"] -> event.key  (load)
        # param["key"] = val -> event.key = val  (store — handled by parent Assign visit)
        if self._is_param(node.value) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            return ast.Attribute(value=_name("event"), attr=node.slice.value, ctx=node.ctx)
        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        # Check pattern BEFORE generic_visit renames param -> event.
        # param.get("key") -> event.key
        # param.get("key", default) -> event.key  (class field provides the default)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and self._is_param(node.func.value)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return ast.Attribute(value=_name("event"), attr=node.args[0].value, ctx=ast.Load())
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.expr:
        # Rename all remaining bare references to the param -> event
        if node.id == self.param_name:
            return _name("event")
        return node


def _transform_callable_body(
    callable_node: ast.expr | ast.stmt,
    force: bool = False,
) -> ast.expr | ast.stmt:
    """Rename event-data param and transform body dict accesses for a lambda or funcdef.

    When *force* is True the second parameter is always treated as event data
    regardless of its name (used for inline condition/replacement lambdas where
    the context guarantees the second param is the event).
    """
    if isinstance(callable_node, ast.Lambda):
        args = callable_node.args.args
        if len(args) >= 2 and (force or args[1].arg in EVENT_PARAM_NAMES):
            old_name = args[1].arg
            args[1].arg = "event"
            callable_node.body = _BodyTransformer(old_name).visit(callable_node.body)
    elif isinstance(callable_node, ast.FunctionDef):
        args = callable_node.args.args
        if len(args) >= 2 and (force or args[1].arg in EVENT_PARAM_NAMES):
            old_name = args[1].arg
            args[1].arg = "event"
            new_body = [_BodyTransformer(old_name).visit(stmt) for stmt in callable_node.body]
            callable_node.body = new_body
    return callable_node


# ---------------------------------------------------------------------------
# Main transformer
# ---------------------------------------------------------------------------

class EventMigrator(ast.NodeTransformer):
    def __init__(self) -> None:
        self.event_classes_used: set[str] = set()
        # Names of functions that are used as condition/replacement args
        self._callable_names_to_transform: set[str] = set()

    # --- First pass: collect function names used as condition/replacement args ---

    def _collect_callable_names(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name not in {"TriggerRegistration", "ReplacementEffect"}:
                continue
            for kw in node.keywords:
                if kw.arg in {"condition", "replacement", "effect"}:
                    if isinstance(kw.value, ast.Name):
                        self._callable_names_to_transform.add(kw.value.id)

    # --- Visits ---

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.stmt:
        self.generic_visit(node)
        # Transform any function whose second param is an event-data name,
        # regardless of whether it was explicitly passed as condition/replacement.
        # This catches closures inside factory functions.
        _transform_callable_body(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        self.generic_visit(node)

        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # --- TriggerRegistration(...) ---
        if func_name == "TriggerRegistration":
            for kw in node.keywords:
                if kw.arg == "event_type":
                    member = _is_eventtype_attr(kw.value)
                    if member and member in EVENTTYPE_TO_CLASS:
                        cls_name = EVENTTYPE_TO_CLASS[member]
                        self.event_classes_used.add(cls_name)
                        kw.value = _name(cls_name)
                elif kw.arg in {"condition", "replacement"}:
                    if isinstance(kw.value, ast.Lambda):
                        _transform_callable_body(kw.value, force=True)
            return node

        # --- ReplacementEffect(...) ---
        if func_name == "ReplacementEffect":
            for kw in node.keywords:
                if kw.arg == "event_type":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        s = kw.value.value
                        if s in STRING_TO_REPLACEMENT_CLASS:
                            cls_name = STRING_TO_REPLACEMENT_CLASS[s]
                            self.event_classes_used.add(cls_name)
                            kw.value = _name(cls_name)
                elif kw.arg in {"condition", "replacement"}:
                    if isinstance(kw.value, ast.Lambda):
                        _transform_callable_body(kw.value, force=True)
            return node

        # --- fire_event(game, EventType.X, {...}) ---
        if func_name == "fire_event":
            # Positional: fire_event(game, EventType.X)  or  fire_event(game, EventType.X, {...})
            if len(node.args) >= 2:
                member = _is_eventtype_attr(node.args[1])
                if member and member in EVENTTYPE_TO_CLASS:
                    cls_name = EVENTTYPE_TO_CLASS[member]
                    self.event_classes_used.add(cls_name)
                    kwargs: list[ast.keyword] = []
                    if len(node.args) >= 3 and isinstance(node.args[2], ast.Dict):
                        kwargs = _dict_to_kwargs(node.args[2])
                    event_call = ast.Call(func=_name(cls_name), args=[], keywords=kwargs)
                    node.args = [node.args[0], event_call]
            return node

        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.stmt | None:
        # Remove EventType (and _ET alias) from benchmarks.sos.workspace.engine.triggers imports.
        # If nothing remains, drop the import entirely.
        if node.module == "engine.triggers":
            new_names = [
                alias for alias in node.names
                if alias.name != "EventType" and alias.asname != "_ET"
            ]
            if not new_names:
                return None  # drop entire import
            node.names = new_names
        return node


# ---------------------------------------------------------------------------
# Import injection
# ---------------------------------------------------------------------------

def _inject_events_import(tree: ast.Module, event_classes: set[str]) -> None:
    """Insert 'from benchmarks.sos.workspace.engine.events import ...' at the top of the module."""
    if not event_classes:
        return

    # Check if engine.events import already exists; if so, merge.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "engine.events":
            existing = {alias.name for alias in node.names}
            for cls in sorted(event_classes - existing):
                node.names.append(ast.alias(name=cls))
            node.names.sort(key=lambda a: a.name)
            return

    # Find insertion point: after the last future/stdlib import at the top.
    insert_at = 0
    for i, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert_at = i + 1
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            # Module docstring
            insert_at = i + 1
        else:
            break

    import_node = ast.ImportFrom(
        module="engine.events",
        names=[ast.alias(name=cls) for cls in sorted(event_classes)],
        level=0,
    )
    tree.body.insert(insert_at, import_node)


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(path: Path, dry_run: bool = False) -> bool:
    """Transform a single file. Returns True if the file was changed."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"  SKIP (parse error): {exc}")
        return False

    migrator = EventMigrator()
    migrator._collect_callable_names(tree)
    new_tree = migrator.visit(tree)
    ast.fix_missing_locations(new_tree)

    if migrator.event_classes_used:
        _inject_events_import(new_tree, migrator.event_classes_used)

    new_source = ast.unparse(new_tree)

    # ast.unparse strips docstrings-as-module-body in some edge cases;
    # if the file didn't change meaningfully, skip.
    if new_source == ast.unparse(ast.parse(source)):
        return False

    if not dry_run:
        path.write_text(new_source + "\n", encoding="utf-8")
    return True


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    targets = [
        ROOT / "cards",
        ROOT / "tests",
    ]

    changed = []
    skipped = []

    for target in targets:
        for path in sorted(target.rglob("*.py")):
            rel = path.relative_to(ROOT)
            print(f"Processing {rel} ...", end=" ")
            if process_file(path, dry_run=dry_run):
                print("CHANGED")
                changed.append(rel)
            else:
                print("ok")
                skipped.append(rel)

    print(f"\n{'DRY RUN — ' if dry_run else ''}Done: {len(changed)} changed, {len(skipped)} unchanged")
    if changed:
        print("Changed files:")
        for p in changed:
            print(f"  {p}")


if __name__ == "__main__":
    main()
