"""Static AST lint-guard over every card implementation.

Some card-impl defects only crash *mid-game* — a bogus enum member or an
undefined name inside a trigger/effect callback passes both import and the
strict loader's instantiation check, then raises the first time that path
runs during a real game (the ``NameError: EventType`` / ``AttributeError:
Layer.ABILITY_ADDING`` class of bug that this phase fixed).

This guard walks each ``card_impl.py`` with :mod:`ast` — no execution — and
fails on four defect classes:

  (a) a ``Layer.X`` / ``SubLayer.X`` attribute that is not a real enum member;
  (b) a bare name that is referenced (loaded) but never bound or imported
      anywhere in the module (catches the ``EventType`` class of bug);
  (c) the misspelled ``sub_layer=`` keyword (the field is ``sublayer``);
  (d) a direct ``<player>.life`` mutation (assignment or augmented
      assignment). Life must move only through ``game.gain_life`` /
      ``game.lose_life`` so the gain/loss triggers fire (Ajani's Pridemate
      et al.); a raw ``player.life += N`` silently bypasses them.

It is intentionally AST-based, not execution-based, so it catches paths that
only run mid-game. It is fast (well under 2s over the full set) and every
finding names the file and line.
"""

from __future__ import annotations

import ast
import builtins
import time
from pathlib import Path

import pytest

from engine.continuous_effects import Layer, SubLayer

_WORKSPACE = Path(__file__).resolve().parents[1]
_CARDS_ROOT = _WORKSPACE / "cards"

_VALID_LAYER = set(Layer.__members__)
_VALID_SUBLAYER = set(SubLayer.__members__)

# Names that are always available without a binding in the module.
_ALLOWED_NAMES = set(dir(builtins)) | {
    "__name__", "__file__", "__doc__", "__class__", "__module__",
    "__qualname__", "__annotations__", "__dict__", "__all__", "__spec__",
    "__loader__", "__package__", "__builtins__",
}


def _collect_bound_names(tree: ast.AST) -> tuple[set[str], bool]:
    """Return (names bound anywhere in the module, saw_wildcard_import).

    Scope is flattened deliberately: we only want to catch names that are
    bound *nowhere*, so being over-permissive about *where* a name is bound
    avoids false positives on closures. A ``from x import *`` makes the bound
    set unknowable, so its presence disables the undefined-name check for that
    module (reported via the returned flag).
    """
    bound: set[str] = set()
    saw_wildcard = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    saw_wildcard = True
                else:
                    bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        # Structural-pattern-match captures (3.10+) also bind names.
        elif isinstance(node, ast.MatchAs) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
    return bound, saw_wildcard


def find_impl_defects(source: str) -> list[tuple[int, str]]:
    """Return ``(lineno, message)`` findings for one card-impl source string.

    The checker used by both the whole-set guard and its self-tests.
    """
    tree = ast.parse(source)
    bound, saw_wildcard = _collect_bound_names(tree)
    findings: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        # (a) Layer.X / SubLayer.X against the real enums.
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "Layer" and node.attr not in _VALID_LAYER:
                findings.append((node.lineno, f"invalid enum member Layer.{node.attr}"))
            elif node.value.id == "SubLayer" and node.attr not in _VALID_SUBLAYER:
                findings.append((node.lineno, f"invalid enum member SubLayer.{node.attr}"))

        # (c) misspelled sub_layer= keyword.
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "sub_layer":
                    findings.append(
                        (node.lineno, "misspelled keyword 'sub_layer=' (the field is 'sublayer')")
                    )

        # (d) direct `.life` mutation — must route through gain_life/lose_life.
        _life_targets: list[ast.expr] = []
        if isinstance(node, ast.AugAssign):
            _life_targets = [node.target]
        elif isinstance(node, ast.Assign):
            _life_targets = list(node.targets)
        for tgt in _life_targets:
            if isinstance(tgt, ast.Attribute) and tgt.attr == "life":
                findings.append(
                    (
                        node.lineno,
                        "direct '.life' mutation — use game.gain_life / game.lose_life",
                    )
                )

        # (b) undefined bare name (skipped when a wildcard import hides bindings).
        if (
            not saw_wildcard
            and isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id not in bound
            and node.id not in _ALLOWED_NAMES
        ):
            findings.append((node.lineno, f"undefined name '{node.id}'"))

    findings.sort()
    return findings


def _all_impl_files() -> list[Path]:
    return sorted(_CARDS_ROOT.glob("**/card_impl.py"))


class TestCardImplAstGuard:
    def test_every_impl_is_clean(self) -> None:
        """No card impl references a bad enum member, undefined name, or
        the misspelled ``sub_layer=`` keyword."""
        problems: list[str] = []
        for path in _all_impl_files():
            for lineno, message in find_impl_defects(path.read_text()):
                rel = path.relative_to(_WORKSPACE)
                problems.append(f"{rel}:{lineno}: {message}")
        assert not problems, "Card-impl AST defects found:\n" + "\n".join(problems)

    def test_guard_is_fast(self) -> None:
        """The whole-set walk must stay well under 2s (it is pure parsing)."""
        start = time.perf_counter()
        for path in _all_impl_files():
            find_impl_defects(path.read_text())
        assert time.perf_counter() - start < 2.0

    def test_finds_at_least_the_full_card_pool(self) -> None:
        """Sanity: the guard actually walks the whole set, not an empty glob."""
        assert len(_all_impl_files()) >= 286


class TestGuardCatchesEachOriginalDefect:
    """Each of the five original defects, as a synthetic snippet, is caught —
    proving the guard would flag them if the fixes were reverted."""

    def _messages(self, source: str) -> list[str]:
        return [m for _, m in find_impl_defects(source)]

    def test_fdn_174_undefined_eventtype(self) -> None:
        # resolve-time hasattr(EventType, 'END_OF_TURN') — EventType never bound.
        src = "def f():\n    if hasattr(EventType, 'END_OF_TURN'):\n        pass\n"
        assert any("undefined name 'EventType'" in m for m in self._messages(src))

    def test_fdn_236_undefined_eventtype(self) -> None:
        src = "def f():\n    if hasattr(EventType, 'COUNTER_ADDED'):\n        pass\n"
        assert any("undefined name 'EventType'" in m for m in self._messages(src))

    def test_fdn_224_ability_adding_default_and_sub_layer(self) -> None:
        src = (
            "from engine.continuous_effects import ContinuousEffect, Layer, SubLayer\n"
            "def f(self, _apply):\n"
            "    return ContinuousEffect(source=self, layer=Layer.ABILITY_ADDING, "
            "sub_layer=SubLayer.DEFAULT, apply=_apply)\n"
        )
        msgs = self._messages(src)
        assert any("Layer.ABILITY_ADDING" in m for m in msgs)
        assert any("SubLayer.DEFAULT" in m for m in msgs)
        assert any("sub_layer=" in m for m in msgs)

    def test_fdn_159_abilities_and_add_ability(self) -> None:
        src = (
            "from engine.continuous_effects import ContinuousEffect, Layer, SubLayer\n"
            "def f(self, _apply):\n"
            "    return ContinuousEffect(source=self, layer=Layer.ABILITIES, "
            "sublayer=SubLayer.ADD_ABILITY, apply=_apply)\n"
        )
        msgs = self._messages(src)
        assert any("Layer.ABILITIES" in m for m in msgs)
        assert any("SubLayer.ADD_ABILITY" in m for m in msgs)

    def test_fdn_219_modification(self) -> None:
        src = (
            "from engine.continuous_effects import ContinuousEffect, Layer, SubLayer\n"
            "def f(self, _apply):\n"
            "    return ContinuousEffect(source=self, layer=Layer.POWER_TOUGHNESS, "
            "sublayer=SubLayer.MODIFICATION, apply=_apply)\n"
        )
        assert any("SubLayer.MODIFICATION" in m for m in self._messages(src))

    def test_direct_life_augassign_is_flagged(self) -> None:
        # player.life += N and player.life -= N both bypass the life triggers.
        src = "def f(game, player):\n    player.life += 3\n    player.life -= 1\n"
        msgs = self._messages(src)
        assert sum("direct '.life' mutation" in m for m in msgs) == 2

    def test_direct_life_assign_is_flagged(self) -> None:
        src = "def f(game, player):\n    player.life = 20\n"
        assert any("direct '.life' mutation" in m for m in self._messages(src))

    def test_gain_life_call_is_not_flagged(self) -> None:
        # The sanctioned path — reading player.life is fine, only mutation is not.
        src = (
            "from engine.game import gain_life, lose_life\n"
            "def f(game, player):\n"
            "    if player.life > 0:\n"
            "        gain_life(game, player, 3)\n"
            "        lose_life(game, player, 1)\n"
        )
        assert not any("direct '.life' mutation" in m for m in self._messages(src))

    def test_valid_members_and_bound_names_are_not_flagged(self) -> None:
        # No false positive on the corrected forms.
        src = (
            "from engine.continuous_effects import ContinuousEffect, Layer, SubLayer\n"
            "from engine.events import EndOfTurnTriggeredEvent\n"
            "def f(self, _apply):\n"
            "    e = EndOfTurnTriggeredEvent()\n"
            "    return ContinuousEffect(source=self, layer=Layer.ABILITY, "
            "sublayer=SubLayer.MODIFY_PT, apply=_apply)\n"
        )
        assert find_impl_defects(src) == []


@pytest.mark.parametrize(
    "card_dir",
    ["fdn_174", "fdn_236", "fdn_224", "fdn_159", "fdn_219", "fdn_58", "spg_79"],
)
def test_previously_broken_impls_are_now_clean(card_dir: str) -> None:
    """The cards this phase fixed (and the two the guard surfaced) are clean."""
    path = _CARDS_ROOT / "fdn" / card_dir / "card_impl.py"
    assert path.is_file()
    assert find_impl_defects(path.read_text()) == []
