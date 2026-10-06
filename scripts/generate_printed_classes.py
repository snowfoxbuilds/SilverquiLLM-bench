"""Generate a card's predefined printed classes from its ``card_spec.json``.

Every card, every face of a multi-face card and every printed ability has a
predefined, behavior-free class (DECISION-MODEL.md › Printed identity; see
ADR-017). This script writes them into the card's ``card_impl.py``:

- one class per printed ability, ``<FaceClass>Ability<N>``, carrying its
  printed text, in a generated block placed after the module's imports;
- with ``--stub`` (or when ``card_impl.py`` is missing), one behavior-free face
  class per face, subclassing the engine's card type class.

A face stub carries its face's printed characteristics as constructor
defaults: name, mana cost (``ManaCost()`` when it has none), every card type
the engine supports (an artifact creature subclasses ``ArtifactCreature``),
subtypes, the Basic, Legendary and Snow supertypes, rules text, and power,
toughness or starting loyalty, with a symbolic value such as ``*`` stubbed as
0. A type line naming no supported card type is rejected.

Each printed line is one ability, except that keywords sharing a line are
separate abilities ("Flying, trample" is two); abilities, modes included, are
numbered in printed order per face. Re-running on an unchanged spec is a no-op.

Usage::

    python3 scripts/generate_printed_classes.py [--stub] CARD_DIR [CARD_DIR ...]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

BLOCK_START = (
    "# region Printed abilities — generated from card_spec.json by "
    "scripts/generate_printed_classes.py; do not edit"
)
BLOCK_END = "# endregion Printed abilities"

# Keywords a spec's ``keywords`` list may omit but that still share a line.
EVERGREEN_KEYWORDS = frozenset({
    "deathtouch", "defender", "double strike", "enchant", "equip", "first strike",
    "flash", "flying", "haste", "hexproof", "indestructible", "lifelink", "menace",
    "protection", "prowess", "reach", "trample", "vigilance", "ward",
})

_CARD_TYPE_BASES = ("ArtifactCreature", "Creature", "Planeswalker", "Artifact", "Enchantment",
                    "Instant", "Sorcery", "Land")
_CARD_TYPES = ("Artifact", "Creature", "Enchantment", "Instant", "Land", "Planeswalker", "Sorcery")
_SUPERTYPES = ("Basic", "Legendary", "Snow")


def class_name(printed_name: str) -> str:
    """``Gleam of Death`` → ``GleamOfDeath``; ``Glamdring, Foe-hammer`` → ``GlamdringFoehammer``."""
    words = re.sub(r"[^A-Za-z0-9 ]", "", printed_name).split()
    return "".join(word[:1].upper() + word[1:] for word in words)


def faces(spec: dict) -> list[dict]:
    return spec.get("card_faces") or [spec]


def _split_outside_parens(line: str) -> list[str]:
    pieces, depth, start = [], 0, 0
    for i, char in enumerate(line):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and line.startswith(", ", i):
            pieces.append(line[start:i])
            start = i + 2
    pieces.append(line[start:])
    return pieces


def _is_keyword(piece: str, keywords: frozenset[str]) -> bool:
    bare = re.sub(r"\(.*?\)", "", piece).strip().lower()
    return any(bare == kw or bare.startswith((kw + " ", kw + "—")) for kw in keywords)


def printed_abilities(oracle_text: str, keywords: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The printed text of each ability on one face, in printed order."""
    known = EVERGREEN_KEYWORDS | {kw.lower() for kw in keywords}
    abilities: list[str] = []
    for line in (oracle_text or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        pieces = _split_outside_parens(line)
        if len(pieces) > 1 and all(_is_keyword(piece, known) for piece in pieces):
            abilities.extend(piece.strip() for piece in pieces)
        else:
            abilities.append(line)
    return abilities


def ability_block(face_classes: list[tuple[str, list[str]]]) -> str:
    """The generated block for ``(face class name, printed abilities)`` pairs."""
    classes = [
        f"class {face}Ability{n}:\n    text = {text!r}\n"
        for face, abilities in face_classes
        for n, text in enumerate(abilities, start=1)
    ]
    return BLOCK_START + "\n\n\n" + "\n\n".join(classes) + "\n\n" + BLOCK_END + "\n"


def _stat(value: str | None) -> int:
    """A printed power, toughness or loyalty; a symbolic one (``*``, ``1+*``, ``X``) is a zero placeholder."""
    return int(value) if value is not None and re.fullmatch(r"-?\d+", value) else 0


def _stub_face(face: dict) -> tuple[str, str]:
    name = face["name"]
    types, _, subtypes = face["type_line"].partition(" — ")
    words = types.split()
    card_types = [t for t in _CARD_TYPES if t in words]
    if not card_types:
        raise ValueError(f"{name!r}: type line {face['type_line']!r} names no supported card type")
    base = "ArtifactCreature" if {"Artifact", "Creature"} <= set(card_types) else next(
        t for t in _CARD_TYPE_BASES if t in card_types)
    cost = face.get("mana_cost") or ""
    values = {"name": repr(name),
              "mana_cost": f"ManaCost.parse({cost!r})" if cost else "ManaCost()",
              "card_types": "{" + ", ".join(f"CardType.{t.upper()}" for t in card_types) + "}",
              "rules_text": repr(face.get("oracle_text", ""))}
    if "Creature" in card_types:
        values.update(base_power=repr(_stat(face.get("power"))),
                      base_toughness=repr(_stat(face.get("toughness"))))
    if base == "Planeswalker":
        values["starting_loyalty"] = repr(_stat(face.get("loyalty")))
    if subtypes:
        values["subtypes"] = "{" + ", ".join(repr(s) for s in subtypes.split()) + "}"
    supertypes = [t for t in _SUPERTYPES if t in words]
    if supertypes:
        values["supertypes"] = "{" + ", ".join(f"Supertype.{t.upper()}" for t in supertypes) + "}"
    defaults = "\n".join(f"            {key!r}: {value}," for key, value in values.items())
    source = (f"class {class_name(name)}({base}):\n"
              '    """Implementation task: see card_spec.json."""\n\n'
              "    def __init__(self, **kwargs):\n        defaults = {\n"
              f"{defaults}\n        }}\n        defaults.update(kwargs)\n        super().__init__(**defaults)\n")
    return base, source


def stub(spec: dict) -> str:
    """A behavior-free ``card_impl.py`` with one class per face."""
    rendered = [_stub_face(face) for face in faces(spec)]
    bases = sorted({base for base, _ in rendered}, key=_CARD_TYPE_BASES.index)
    return (f"from engine.card import {', '.join(bases)}\n"
            "from engine.types import CardType, ManaCost, Supertype\n\n\n"
            + "\n\n".join(source for _, source in rendered))


def _top_level_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
        elif (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            names.append(node.targets[0].id)
    return names


def implementation_class(source: str, printed_name: str) -> str:
    """The module-level name the card's implementation class is bound to."""
    names = [n for n in _top_level_names(ast.parse(source)) if not re.search(r"Ability\d+$", n)]
    wanted = class_name(printed_name)
    if wanted in names:
        return wanted
    folded = [n for n in names if n.lower() == wanted.lower()]
    if len(folded) == 1:
        return folded[0]
    quoted = [n for n in names if re.search(
        rf"^(class {n}\b|{n} = ).*?[\"']{re.escape(printed_name)}[\"']", source, re.MULTILINE | re.DOTALL)]
    if len(quoted) == 1:
        return quoted[0]
    raise ValueError(f"cannot identify the class for {printed_name!r} among {names}")


def _without_block(source: str) -> str:
    start = source.find(BLOCK_START)
    if start < 0:
        return source
    end = source.index(BLOCK_END, start) + len(BLOCK_END)
    return source[:start].rstrip("\n") + "\n\n\n" + source[end:].lstrip("\n")


def _header_end(source: str) -> int:
    """Offset just after the module docstring, imports and TYPE_CHECKING block."""
    tree = ast.parse(source)
    end_line = 0
    for i, node in enumerate(tree.body):
        is_docstring = i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        is_type_checking = isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test)
        if not (is_docstring or is_type_checking or isinstance(node, (ast.Import, ast.ImportFrom))):
            break
        end_line = node.end_lineno or end_line
    lines = source.splitlines(keepends=True)
    return sum(len(line) for line in lines[:end_line])


def with_block(source: str, block: str) -> str:
    source = _without_block(source)
    cut = _header_end(source)
    head, tail = source[:cut].rstrip("\n"), source[cut:].lstrip("\n")
    parts = [part for part in (head, block.rstrip("\n"), tail.rstrip("\n")) if part]
    return "\n\n\n".join(parts) + "\n"


def render(card_dir: Path, *, make_stub: bool = False) -> str:
    """``card_dir``'s ``card_impl.py`` with its printed classes generated."""
    spec = json.loads((card_dir / "card_spec.json").read_text())
    impl = card_dir / "card_impl.py"
    original = impl.read_text() if impl.exists() else ""
    source = stub(spec) if make_stub or not original else original
    keywords = spec.get("keywords") or []
    card_faces = faces(spec)
    if len(card_faces) == 1:
        face_names = [implementation_class(source, card_faces[0]["name"])]
    else:
        face_names = [class_name(face["name"]) for face in card_faces]
    face_classes = [
        (face_name, printed_abilities(face.get("oracle_text", ""), keywords))
        for face_name, face in zip(face_names, card_faces)
    ]
    if any(abilities for _, abilities in face_classes):
        return with_block(source, ability_block(face_classes))
    return _without_block(source).rstrip("\n") + "\n"


def generate(card_dir: Path, *, make_stub: bool = False) -> bool:
    """Write ``card_dir``'s printed classes; return whether the file changed."""
    impl = card_dir / "card_impl.py"
    updated = render(card_dir, make_stub=make_stub)
    if impl.exists() and impl.read_text() == updated:
        return False
    impl.write_text(updated)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stub", action="store_true",
                        help="overwrite card_impl.py with a behavior-free stub first")
    parser.add_argument("card_dirs", nargs="+", type=Path)
    args = parser.parse_args()
    changed = [d for d in args.card_dirs if generate(d, make_stub=args.stub)]
    print(f"{len(changed)} of {len(args.card_dirs)} card_impl.py files changed")


if __name__ == "__main__":
    main()
