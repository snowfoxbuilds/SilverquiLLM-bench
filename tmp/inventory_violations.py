"""Inventory audited-test philosophy violations + oracle-impl status.

For each audited test dir under benchmarks/sos/data/tests/audited/sos/, report:
  - which known non-canonical coupling symbols appear (with line numbers)
  - whether a non-stub oracle impl exists for that card

A non-stub oracle impl = a card_impl.py whose class defines a non-dunder method
(same definition the validation harness uses).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AUDITED = REPO / "benchmarks/sos/data/tests/audited/sos"
ORACLE_CARDS = REPO / "benchmarks/sos/data/test_oracle_workspace/cards/sos"

# Known non-canonical coupling patterns from the triage report.
# Each: name -> regex. Single-leading-underscore card attrs + invented hooks +
# oracle-only methods + engine-internal smells (Part C).
PATTERNS = {
    "activate(ability_index=": re.compile(r"\.activate\(\s*[^)]*ability_index\s*="),
    "_prepared": re.compile(r"\._prepared\b"),
    "can_cast_from_exile": re.compile(r"\.can_cast_from_exile\b"),
    "get_alternative_cost": re.compile(r"\.get_alternative_cost\b"),
    "register_paradigm_trigger": re.compile(r"\.register_paradigm_trigger\b"),
    "_resolve_targets": re.compile(r"\._resolve_targets\b"),
    "_resolve_target": re.compile(r"\._resolve_target\b(?!s)"),
    "set_targets(": re.compile(r"\.set_targets\("),
    "_targets=": re.compile(r"\._targets\b"),
    "on_enter_battlefield": re.compile(r"\.on_enter_battlefield\("),
    "on_spell_cast": re.compile(r"\.on_spell_cast\("),
    "on_attack": re.compile(r"\.on_attack\("),
    "get_adjusted_cost": re.compile(r"\.get_adjusted_cost\("),
    "_cast_via_flashback": re.compile(r"\._cast_via_flashback\b"),
    # Part C engine-internal smells
    "stack._items": re.compile(r"\.stack\._items\b"),
    "trigger_manager._triggers": re.compile(r"\.trigger_manager\._triggers\b"),
    "_script.appendleft": re.compile(r"\._script\.appendleft\b"),
    "_script.extend": re.compile(r"\._script\.extend\b"),
    "_script(other)": re.compile(r"\._script\.(?!appendleft\b|extend\b)\w+"),
}


def is_stub(impl_path: Path) -> bool:
    if not impl_path.exists():
        return True
    try:
        tree = ast.parse(impl_path.read_text())
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("__"):
                    return False
    return True


def main() -> None:
    rows = []
    for d in sorted(AUDITED.iterdir()):
        if not d.is_dir():
            continue
        tp = d / "tests.py"
        if not tp.exists():
            continue
        text = tp.read_text()
        hits = {}
        for name, rx in PATTERNS.items():
            lines = [i + 1 for i, ln in enumerate(text.splitlines()) if rx.search(ln)]
            if lines:
                hits[name] = lines
        if not hits:
            continue
        impl = ORACLE_CARDS / d.name / "card_impl.py"
        stub = is_stub(impl)
        rows.append((d.name, stub, hits))

    # Partition
    with_oracle = [r for r in rows if not r[1]]
    stub_oracle = [r for r in rows if r[1]]

    print(f"TOTAL coupled files: {len(rows)}")
    print(f"  with NON-STUB oracle impl (validatable): {len(with_oracle)}")
    print(f"  with STUB/absent oracle impl (NOT validatable): {len(stub_oracle)}")
    print()

    # Symbol frequency
    from collections import Counter
    freq = Counter()
    freq_validatable = Counter()
    for name, stub, hits in rows:
        for k in hits:
            freq[k] += 1
            if not stub:
                freq_validatable[k] += 1
    print("=== symbol frequency (all coupled files / validatable subset) ===")
    for k, c in freq.most_common():
        print(f"  {k:28s} {c:4d}  / validatable {freq_validatable.get(k,0)}")
    print()

    print("=== coupled files WITH non-stub oracle impl (these we can fix+validate now) ===")
    for name, stub, hits in with_oracle:
        syms = ", ".join(f"{k}@{v}" for k, v in hits.items())
        print(f"  {name}: {syms}")
    print()
    print(f"=== coupled files with STUB oracle ({len(stub_oracle)}) — names only ===")
    print("  " + " ".join(n for n, _, _ in stub_oracle))


if __name__ == "__main__":
    main()
