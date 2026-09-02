"""Static AST lint-guard over every card implementation.

Some card-impl defects only crash *mid-game* — a bogus enum member or an
undefined name inside a trigger/effect callback passes both import and the
strict loader's instantiation check, then raises the first time that path
runs during a real game (the ``NameError: EventType`` / ``AttributeError:
Layer.ABILITY_ADDING`` class of bug that this phase fixed).

This guard walks each ``card_impl.py`` with :mod:`ast` — no execution — and
fails on the following defect classes (plus (h), the text-gated
enters-with-counters revert, checked separately below):

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
  (g) a write to a card-private counter stash — any ``.<name>_counter`` /
      ``.<name>_counters`` attribute other than the sanctioned engine fields
      (``plus_one_counters`` / ``minus_one_counters`` and their ``_base_*``
      shadows, and ``_generic_counters``). Counters are a real engine primitive:
      a private ``self.incubation_counters`` int is invisible to ``.counters``,
      to state comparison, and to the replay executor's ``CounterAdded`` sync.
      Use ``engine.game.add_counter`` / ``remove_counter`` (read via
      ``.counters``). Covers the plain, augmented, and *annotated* assignment
      forms (``self.x_counters: int = 0``).
  (i) a ``copy.copy(...)`` / ``copy.deepcopy(...)`` call. Copying a card/permanent
      this way skips ``__init__``, so the clone shares the original's
      ``object_id`` (a latent bug for the ``object_id``-keyed per-turn loyalty
      tracker in ``abilities.py``) and — for ``copy.copy`` — aliases its mutable
      characteristic containers. Token copies go through
      ``engine.game.mint_token_copy`` (fresh identity, de-aliased containers,
      counters/damage/tap reset per rule 707.2); plain containers copy with
      ``list()`` / ``dict()`` / ``set()``.

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

# The engine's own counter storage. Every *other* ``*_counter(s)`` attribute a
# card assigns is a private stash the engine (and the replay executor's
# CounterAdded sync) cannot see — counters must flow through add_counter /
# remove_counter and be read via ``.counters``.
_ENGINE_COUNTER_ATTRS = {
    "plus_one_counters",
    "minus_one_counters",
    "_base_plus_one_counters",
    "_base_minus_one_counters",
    "_generic_counters",
}

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


def _iter_add_counter_calls(node: ast.AST):
    """Yield ``add_counter(...)`` call nodes anywhere under *node*."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            fn = n.func
            if (isinstance(fn, ast.Name) and fn.id == "add_counter") or (
                isinstance(fn, ast.Attribute) and fn.attr == "add_counter"
            ):
                yield n


def _has_self_etb_marker(node: ast.AST) -> bool:
    """True if *node* contains a self-ETB identity check ``<x>.permanent is <name>``.

    This is the signature of a "this permanent enters" trigger condition (rule
    603.3a self-entry), e.g. ``event.permanent is source``. It deliberately does
    NOT match ``permanent is None`` (a bare-name None guard) or a landfall/other
    condition that inspects the *entering* object's characteristics, so a
    legitimate "whenever a land you control enters" doubler is not flagged.
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Is):
            left = n.left
            comp = n.comparators[0]
            if (
                isinstance(left, ast.Attribute)
                and left.attr == "permanent"
                and isinstance(comp, ast.Name)
            ):
                return True
    return False


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
        elif isinstance(node, ast.AnnAssign):
            # Annotated assignment (``self.x_counters: int = 0``) still binds the
            # attribute; only the counter-stash rule needs the annotated form.
            _assign_targets = [node.target]
        for tgt in _assign_targets:
            if not isinstance(tgt, ast.Attribute):
                continue
            # The life/tapped rules apply to plain/augmented assignment only.
            if not isinstance(node, ast.AnnAssign):
                if tgt.attr == "life":
                    findings.append(
                        (
                            node.lineno,
                            "direct '.life' mutation — use game.gain_life / game.lose_life",
                        )
                    )
                if tgt.attr == "tapped":
                    findings.append((
                        node.lineno,
                        ("'.tapped' write — the engine field is 'is_tapped' "
                         "(or use engine.game.tap / untap)"),
                    ))
            # (g) private counter stash — any `*_counter(s)` attribute that is
            # not one of the engine's own counter fields.
            if (
                (tgt.attr.endswith("_counter") or tgt.attr.endswith("_counters"))
                and tgt.attr not in _ENGINE_COUNTER_ATTRS
            ):
                findings.append((
                    node.lineno,
                    (f"private counter stash '.{tgt.attr}' — counters are an "
                     "engine primitive (engine.game.add_counter / remove_counter, "
                     "read via .counters)"),
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

        # (i) copy.copy / copy.deepcopy of a game object. A shallow/deep copy
        #     skips ``__init__``, so the clone shares the original's ``object_id``
        #     (a latent bug for per-object ability tracking — two objects count as
        #     one for the once-per-turn loyalty limit) and, for copy.copy, aliases
        #     the original's mutable characteristic containers. Token copies must
        #     go through engine.game.mint_token_copy (fresh identity, de-aliased
        #     containers, counters/damage/tap reset per rule 707.2); plain
        #     containers copy with list() / dict() / set().
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("copy", "deepcopy")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "copy"
        ):
            findings.append((
                node.lineno,
                (f"copy.{node.func.attr}(...) — a shallow/deep copy skips "
                 "__init__, so the clone shares the original's object_id; mint "
                 "token copies via engine.game.mint_token_copy (copy plain "
                 "containers with list() / dict() / set())"),
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
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and (key.value.endswith("_counter") or key.value.endswith("_counters"))
                    and key.value not in _ENGINE_COUNTER_ATTRS
                ):
                    findings.append((
                        node.lineno,
                        (f"private counter stash '{key.value}' via setattr — "
                         "counters are an engine primitive (add_counter / "
                         "remove_counter, read via .counters)"),
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

    # (h) enters-with-counters revert: a card whose oracle text says it "enters
    # with … counter(s)" (rule 614.1c) must land those counters through the
    # enters_battlefield_with replacement hook — never re-add them via on_resolve
    # or a self-ETB trigger (both let the permanent exist transiently without the
    # counters, so a 0/0 dies to SBAs before they land). The text gate keeps this
    # off cards that only add counters later (landfall doublers, +1/+1 synergy).
    low = source.lower()
    if "enters with" in low and "counter" in low:
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if fn.name == "on_resolve":
                for call in _iter_add_counter_calls(fn):
                    findings.append((
                        call.lineno,
                        (
                            "(h) entry counters via on_resolve add_counter — an "
                            "'enters with … counter(s)' card must land them "
                            "through the enters_battlefield_with hook (rule "
                            "614.1c), not on_resolve"
                        ),
                    ))
            elif fn.name == "register_triggers" and _has_self_etb_marker(fn):
                for call in _iter_add_counter_calls(fn):
                    findings.append((
                        call.lineno,
                        (
                            "(h) entry counters via a self-ETB trigger "
                            "add_counter — use the enters_battlefield_with hook "
                            "(rule 614.1c), not a self-entering triggered ability"
                        ),
                    ))

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

    def test_h_enters_with_counters_on_resolve_revert_is_flagged(self) -> None:
        # Reverting Wildwood/Mossborn/Goblin Boarders to landing entry counters
        # in on_resolve must be caught.
        src = (
            "class C:\n"
            "    '''This creature enters with X +1/+1 counters on it.'''\n"
            "    def on_resolve(self, game):\n"
            "        from engine.game import add_counter\n"
            "        add_counter(game, self, '+1/+1', self.x_value)\n"
        )
        assert any(
            "enters_battlefield_with hook" in m and "on_resolve" in m
            for m in self._messages(src)
        )

    def test_h_enters_with_counters_self_etb_trigger_revert_is_flagged(self) -> None:
        # Reverting Gnarlid to a self-ETB trigger that adds the entry counters.
        src = (
            "class C:\n"
            "    '''If this creature was kicked, it enters with two +1/+1 "
            "counters on it.'''\n"
            "    def register_triggers(self, game):\n"
            "        from engine.game import add_counter\n"
            "        from engine.triggers import TriggerRegistration\n"
            "        source = self\n"
            "        def _cond(game, event):\n"
            "            return event.permanent is source\n"
            "        def _eff(g):\n"
            "            add_counter(g, source, '+1/+1', 2)\n"
            "        game.trigger_manager.register(TriggerRegistration(\n"
            "            event_type=None, condition=_cond, effect=_eff, source=self))\n"
        )
        assert any(
            "enters_battlefield_with hook" in m and "self-ETB" in m
            for m in self._messages(src)
        )

    def test_h_landfall_doubler_to_self_is_not_flagged(self) -> None:
        # Mossborn's landfall doubling adds counters to itself when a LAND
        # enters — legitimate, not an entry counter. No self-ETB identity marker,
        # so it must NOT be flagged even though the text says "enters with".
        src = (
            "class C:\n"
            "    '''This creature enters with a +1/+1 counter on it. Landfall — "
            "double its +1/+1 counters.'''\n"
            "    def enters_battlefield_with(self, game, event):\n"
            "        event.counters['+1/+1'] = 1\n"
            "    def register_triggers(self, game):\n"
            "        from engine.game import add_counter\n"
            "        source = self\n"
            "        def _cond(game, event):\n"
            "            permanent = event.permanent\n"
            "            if permanent is None:\n"
            "                return False\n"
            "            return 'land' in permanent.card_types\n"
            "        def _eff(g):\n"
            "            add_counter(g, source, '+1/+1', source.plus_one_counters)\n"
        )
        assert not any("enters_battlefield_with hook" in m for m in self._messages(src))

    def test_h_enters_with_counters_hook_form_is_not_flagged(self) -> None:
        # The sanctioned form — landing entry counters on the replacement event.
        src = (
            "class C:\n"
            "    '''This creature enters with X +1/+1 counters on it.'''\n"
            "    def enters_battlefield_with(self, game, event):\n"
            "        if self.x_value > 0:\n"
            "            event.counters['+1/+1'] = self.x_value\n"
        )
        assert not any("enters_battlefield_with hook" in m for m in self._messages(src))

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

    # (g) private counter stashes.
    def test_annotated_counter_stash_is_flagged(self) -> None:
        # The exact form Drake Hatcher / Nine-Lives Familiar used.
        src = "class C:\n    def __init__(self):\n        self.incubation_counters: int = 0\n"
        assert any("private counter stash '.incubation_counters'" in m
                   for m in self._messages(src))

    def test_augmented_counter_stash_is_flagged(self) -> None:
        src = "def f(self, src):\n    src.soul_counters += 1\n"
        assert any("private counter stash '.soul_counters'" in m
                   for m in self._messages(src))

    def test_plain_counter_stash_assign_is_flagged(self) -> None:
        src = "def f(self, src):\n    src.revival_counters = 8\n"
        assert any("private counter stash '.revival_counters'" in m
                   for m in self._messages(src))

    def test_singular_counter_stash_is_flagged(self) -> None:
        src = "def f(self, src):\n    src.charge_counter = 2\n"
        assert any("private counter stash '.charge_counter'" in m
                   for m in self._messages(src))

    def test_setattr_counter_stash_is_flagged(self) -> None:
        src = "def f(self, src):\n    setattr(src, 'bait_counters', 3)\n"
        assert any("bait_counters" in m and "setattr" in m
                   for m in self._messages(src))

    def test_engine_counter_fields_are_not_flagged(self) -> None:
        # The sanctioned engine fields must NOT trip the stash rule.
        src = (
            "class C:\n"
            "    def __init__(self):\n"
            "        self.plus_one_counters: int = 0\n"
            "        self.minus_one_counters: int = 0\n"
            "    def f(self):\n"
            "        self._generic_counters.clear()\n"
        )
        assert not any("counter stash" in m for m in self._messages(src))

    def test_reading_dot_counters_is_not_flagged(self) -> None:
        # Reading the sanctioned `.counters` view is the correct pattern.
        src = "def f(self, src):\n    return src.counters.get('soul', 0)\n"
        assert not any("counter stash" in m for m in self._messages(src))

    # (i) copy.copy / copy.deepcopy of a game object.
    def test_fdn_154_copy_copy_revert_is_flagged(self) -> None:
        # Reverting Extravagant Replication to a bare shallow copy of the chosen
        # permanent must be caught (the copy would share the original's object_id).
        src = (
            "import copy\n"
            "def f(game, ctrl, chosen):\n"
            "    from engine.game import create_token\n"
            "    token = copy.copy(chosen)\n"
            "    token.is_token = True\n"
            "    create_token(game, ctrl, token)\n"
        )
        assert any("copy.copy(...)" in m for m in self._messages(src))

    def test_fdn_163_copy_copy_revert_is_flagged(self) -> None:
        # Reverting Self-Reflection to a bare shallow copy of the target creature.
        src = (
            "import copy\n"
            "def on_resolve(self, game):\n"
            "    from engine.game import create_token\n"
            "    token = copy.copy(self.chosen_targets[0])\n"
            "    create_token(game, self.controller, token)\n"
        )
        assert any("copy.copy(...)" in m for m in self._messages(src))

    def test_copy_deepcopy_is_flagged(self) -> None:
        # A deep copy also skips __init__ (shared object_id) — likewise banned.
        src = "import copy\ndef f(x):\n    return copy.deepcopy(x)\n"
        assert any("copy.deepcopy(...)" in m for m in self._messages(src))

    def test_mint_token_copy_is_not_flagged(self) -> None:
        # The sanctioned primitive must NOT be flagged.
        src = (
            "def f(game, ctrl, chosen):\n"
            "    from engine.game import create_token, mint_token_copy\n"
            "    token = mint_token_copy(chosen)\n"
            "    create_token(game, ctrl, token)\n"
        )
        assert not any("copy." in m for m in self._messages(src))

    def test_plain_container_copies_are_not_flagged(self) -> None:
        # Copying plain containers with the builtins is fine — only copy.copy /
        # copy.deepcopy are banned, not a set()/dict()/list() of an attribute.
        src = (
            "def f(self, obj):\n"
            "    types = set(obj.card_types)\n"
            "    counts = dict(obj._generic_counters)\n"
            "    return list(types) + list(counts)\n"
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
