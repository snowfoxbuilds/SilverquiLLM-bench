"""Static AST lint-guard over every card implementation.

Some card-impl defects only crash *mid-game* — a bogus enum member or an
undefined name inside a trigger/effect callback passes both import and the
strict loader's instantiation check, then raises the first time that path
runs during a real game (the ``NameError: EventType`` / ``AttributeError:
Layer.ABILITY_ADDING`` class of bug that this phase fixed).

This guard walks each ``card_impl.py`` with :mod:`ast` — no execution — and
fails on seven defect classes:

  (a) a ``Layer.X`` / ``SubLayer.X`` attribute that is not a real enum member;
  (b) a bare name that is referenced (loaded) but never bound or imported
      anywhere in the module (catches the ``EventType`` class of bug);
  (c) the misspelled ``sub_layer=`` keyword (the field is ``sublayer``);
  (d) a direct ``<player>.life`` mutation (assignment or augmented
      assignment). Life must move only through ``game.gain_life`` /
      ``game.lose_life`` so the gain/loss triggers fire (Ajani's Pridemate
      et al.); a raw ``player.life += N`` silently bypasses them.
  (e) a read of the dead-target backdoors ``_current_target`` /
      ``_resolve_target`` (attribute load or ``getattr(..., "_current_target")``).
      Nothing assigns these; targets flow through ``get_targets`` (spells),
      the ``targeting`` hook (activated/loyalty abilities), or ``choose_object``
      (resolution-time choices). A card reading them silently no-ops.
  (f) a write to ``.tapped`` (assignment/augmented-assignment or
      ``setattr(x, "tapped", …)``). The engine field is ``is_tapped``; a
      ``.tapped`` write is invisible to state comparison and wrong for
      ``GameRef`` matching. Use ``is_tapped`` or ``engine.game.tap`` / ``untap``.

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

# Dead test backdoors: nothing in the engine assigns these, so a card reading
# one silently no-ops. Targets flow through the real channels instead.
_DEAD_TARGET_ATTRS = {"_current_target", "_resolve_target"}

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
        # (f) `.tapped` write — the engine field is `is_tapped`.
        _assign_targets: list[ast.expr] = []
        if isinstance(node, ast.AugAssign):
            _assign_targets = [node.target]
        elif isinstance(node, ast.Assign):
            _assign_targets = list(node.targets)
        for tgt in _assign_targets:
            if isinstance(tgt, ast.Attribute) and tgt.attr == "life":
                findings.append(
                    (
                        node.lineno,
                        "direct '.life' mutation — use game.gain_life / game.lose_life",
                    )
                )
            if isinstance(tgt, ast.Attribute) and tgt.attr == "tapped":
                findings.append((
                    node.lineno,
                    ("'.tapped' write — the engine field is 'is_tapped' "
                     "(or use engine.game.tap / untap)"),
                ))

        # (e) dead-target backdoor reads: `_current_target` / `_resolve_target`.
        #     Nothing assigns these — a card reading one silently no-ops.
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and node.attr in _DEAD_TARGET_ATTRS
        ):
            findings.append((
                node.lineno,
                (f"dead-target backdoor read '{node.attr}' — targets flow "
                 "through get_targets / targeting / choose_object"),
            ))

        # (e'/f') the same defects via getattr/setattr string literals.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = node.func.id
            if fn == "getattr" and len(node.args) >= 2:
                key = node.args[1]
                if isinstance(key, ast.Constant) and key.value in _DEAD_TARGET_ATTRS:
                    findings.append((
                        node.lineno,
                        (f"dead-target backdoor read '{key.value}' via getattr — "
                         "targets flow through the real channels"),
                    ))
            if fn == "setattr" and len(node.args) >= 2:
                key = node.args[1]
                if isinstance(key, ast.Constant) and key.value == "tapped":
                    findings.append((
                        node.lineno,
                        ("setattr '.tapped' — the engine field is 'is_tapped' "
                         "(or use engine.game.tap / untap)"),
                    ))

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

    # (e) dead-target backdoor reads.
    def test_current_target_attribute_read_is_flagged(self) -> None:
        src = "def f(self):\n    t = self._current_target\n    return t\n"
        assert any("_current_target" in m for m in self._messages(src))

    def test_resolve_target_attribute_read_is_flagged(self) -> None:
        src = "def f(self):\n    return self._resolve_target\n"
        assert any("_resolve_target" in m for m in self._messages(src))

    def test_current_target_getattr_is_flagged(self) -> None:
        src = "def f(self):\n    return getattr(self, '_current_target', None)\n"
        assert any("_current_target" in m for m in self._messages(src))

    def test_resolve_target_getattr_is_flagged(self) -> None:
        src = "def f(self):\n    return getattr(self, '_resolve_target', None)\n"
        assert any("_resolve_target" in m for m in self._messages(src))

    def test_chosen_targets_is_not_flagged(self) -> None:
        # The sanctioned target channel must NOT be flagged.
        src = "def f(self):\n    return getattr(self, 'chosen_targets', None)\n"
        assert not any("backdoor" in m for m in self._messages(src))

    # (f) `.tapped` writes.
    def test_tapped_assign_is_flagged(self) -> None:
        src = "def f(self, obj):\n    obj.tapped = True\n"
        assert any("'.tapped' write" in m for m in self._messages(src))

    def test_tapped_setattr_is_flagged(self) -> None:
        src = "def f(self, obj):\n    setattr(obj, 'tapped', True)\n"
        assert any("setattr '.tapped'" in m for m in self._messages(src))

    def test_is_tapped_write_is_not_flagged(self) -> None:
        # The correct field is fine.
        src = "def f(self, obj):\n    obj.is_tapped = True\n"
        assert not any("tapped" in m for m in self._messages(src))

    def test_reading_tapped_is_not_flagged(self) -> None:
        # Only writes are banned; a read (wrong, but out of scope here) is not
        # flagged by the write rule.
        src = "def f(self, obj):\n    return obj.is_tapped\n"
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
