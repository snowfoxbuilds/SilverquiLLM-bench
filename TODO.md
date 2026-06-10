---

# Mission

Implement the MSH Player Query / Player Decision protocol natively in the MSH workspace engine, replace the V1 two-channel `DeterministicPlayer` with the intent-based one, migrate the existing FDN card implementations and their colocated reference tests to the new engine, and adapt FDN replay validation to drive the new engine through the intent-based `DeterministicPlayer` — using the 17lands FDN replay corpus as ground-truth validation of both the new engine protocol and the migrated FDN implementations.

This is **task #1 of the MSH benchmark**: no MSH oracle or audited-test work may begin until this lands. Everything here happens inside `benchmarks/msh/` and (for replay) `silverquillm/replay/`. **`benchmarks/sos/`**** is frozen — do not touch any file under it.**

# Required reading (in order, before writing any code)

1. `docs/specs/MSH-DECISION-MODEL.md` — the canonical design. Every type, matching rule, and lifecycle below is specified there; the spec wins over this prompt on any conflict.
2. `docs/specs/MSH-BENCHMARK.md` — repo layout, what is shared vs. duplicated, SOS freeze, settled decisions.
3. `CONTEXT.md` — glossary. Use these terms exactly in code, docstrings, and docs: **Player Query**, **Player Decision**, **Game Symbols**, **Game Refs**, **Modifiers**, **Intent**, **Baseline Intent**, **DeterministicPlayer (MSH)**.
4. `benchmarks/msh/workspace/engine/player.py` — the V1 protocol you are replacing (the `Player` ABC with `choose_target` / `choose` / `choose_yes_no` / `choose_card` / `assign_damage_order`, and the script-deque `DeterministicPlayer` with `ScriptExhaustedError`).
5. `benchmarks/msh/workspace/test_utils.py` and `test_utils.md` — the V1 two-channel test API being deleted.
6. `silverquillm/replay/DIRECTORY_SUMMARY.md`, then `parser.py`, `executor.py`, `validation.py` — the replay validation pipeline you will adapt.
7. `KEY_DECISIONS.md` workflow in the root `AGENTS.md` — log new decisions as you make them.
# Ground rules

- **No V1 compatibility layer.** The Player Query protocol is the engine's native interaction surface. Do not write an adapter that translates queries back into `choose_*` calls. Delete the V1 helpers; do not deprecate them.
- **The engine stays deterministic and imperative.** Intents exist only on the test/player side. The action layer (cast this, activate that) remains directive-driven; only the *choice* layer becomes query-driven.
- **Naming is binding.** The new player class keeps the name `DeterministicPlayer` (it is glossary-scoped as DeterministicPlayer (MSH)). Do not invent names like IntentPlayer.
- **SOS stays green.** `benchmarks/sos/**` is untouched, and the repo-level SOS validation harness and platform tests must still pass at the end.
- When the spec and this prompt leave a micro-decision open, decide, implement, and record the decision in `KEY_DECISIONS.md`. Most micro-decisions are already locked in the next section — implement those exactly; do not re-litigate them.
# Locked decisions (pre-made — implement exactly)

These were open micro-decisions; they are now decided. Do not redesign them. Record each in `KEY_DECISIONS.md` as "locked by prompt".

**Module layout** (locked):

- `engine/decisions.py` — `DecisionKind`, `PlayerDecision`, `GameRef`, `satisfies()`, ref subset matching, the Game Symbols vocabulary (per-kind attr schema plus canonical Modifier names), and the exception hierarchy.
- `engine/queries.py` — `PlayerQuery`, `Answer`, boundary validation.
- `engine/refs_registry.py` — Game Refs registry.
- `engine/player.py` — only the `Player` ABC with the single `answer` method.
- `engine/intent_player.py` — `Intent`, `DeterministicPlayer`, the query transcript. Re-export `DeterministicPlayer` from `engine/__init__.py`.
**Exception hierarchy** (locked — these names, this engine/test split):

```python
# engine/decisions.py
class ProtocolError(Exception): ...            # base: engine-side protocol failure (attributable to the engine)
class UnknownKindError(ProtocolError): ...     # query kind is not a DecisionKind
class MalformedAttrsError(ProtocolError): ...  # attr key/value outside the blessed per-kind schema
class InvalidOptionsError(ProtocolError): ...  # empty options with min > 0, malformed option, unstable order

class IntentError(Exception): ...              # base: test-authoring failure (attributable to the test)
class AmbiguousIntentError(IntentError): ...   # two active intents matched one query
class UnmatchedQueryError(IntentError): ...    # no card intent and no baseline intent matched
class InvalidAnswerError(IntentError): ...     # answer violates min/max or options membership
class PostconditionError(IntentError): ...     # end_intent postcondition failed
```

**Answer / decline representation** (locked):

```python
# engine/queries.py
@dataclass(frozen=True)
class Answer:
    selected: tuple[PlayerDecision, ...]  # each element equals one of query.options
# Decline is Answer(selected=()) and is legal iff query.min == 0. No separate Decline type.
```

The engine validates every Answer before applying it: `min <= len(selected) <= max`, every element equal to one of `query.options`, no duplicates. A violation raises `InvalidAnswerError` — it is a test bug, not an engine bug.

**Ordering queries** (locked): `min == max == len(options)`; the order of `Answer.selected` is the assignment order.

**Intent shape** (locked):

```python
# engine/intent_player.py
@dataclass(frozen=True)
class Intent:
    pattern: GameRef                                       # matched against query source refs (subset rule per field)
    preferences: tuple[PlayerDecision, ...]                # scanned in order; first satisfied AND offered option wins
    postcondition: Callable[["Game"], bool] | None = None  # checked at end_intent; None = no postcondition
# start_intent(name, intent) / end_intent(name): the name is the registry key, not a field on Intent.
```

**Baseline Intent** (locked): a regular `Intent` with an empty `pattern` (matches everything), held in a dedicated slot on the player and consulted only when no card intent matches. At most one baseline may be set at a time.

**KEY_**[**DECISIONS.md**](http://decisions.md/)** entry format** (locked): one entry per decision — date, decision (one sentence), why (one sentence), rejected alternative (one sentence).

# Execution discipline

- Execute phases strictly in order. Do not start a phase before the previous phase's gate passes.
- One commit (or commit series) per phase, message prefixed `msh-task1 phase N:`.
- Phase gates:
  - 0 → 1: `benchmarks/msh/PHASE0_CALLSITES.md` committed (one row per call site: file, line, V1 method, the query kind it becomes), plus the baseline replay report and passing-test inventory.
  - 1 → 2: data-layer unit tests in `engine_tests/` green.
  - 2 → 3: every checklist row marked converted; grep for the five V1 method names returns nothing under `engine/`.
  - 3 → 4: `test_utils.py` rewritten and importable; workspace docs updated.
  - 4 → 5: all FDN reference tests green.
  - 5 → 6: `engine_tests/` green; `DROPPED_COVERAGE.md` committed.
  - 6 → done: parity report committed; final self-check passes.
- Re-read the Acceptance criteria at the end of every phase. Never declare the task done until all seven hold and the final self-check has been re-run verbatim.
- Code follows spec, never the reverse: do not edit `docs/specs/**` to match your implementation. If you believe the spec is wrong, log it in `KEY_DECISIONS.md` as an open question and implement the spec as written.
# Phase 0 — Recon and baseline

- Map every call site of the five V1 `Player` methods across `benchmarks/msh/workspace/engine/` (expect them at least in `casting.py`, `combat.py`, `triggers.py`, `replacement_effects.py`, `mana.py`, `stack.py`, `state_based_actions.py`) and across `cards/fdn/*/card_impl.py` and `cards/fdn/*/tests.py`. Produce a checklist; every call site must be converted by Phase 2/4.
- Run the FDN replay validation CLI against the V1 engine on the available FDN replay corpus and **record the baseline report** (divergence counts by type, per file). This is the parity bar for Phase 6.
- Run `engine_tests/` and the FDN reference tests; record the passing set. This is the coverage bar for Phase 5.
# Phase 1 — Decision model core (new modules in `benchmarks/msh/workspace/engine/`)

Create the data layer exactly as specified in [MSH-DECISION-MODEL.md](http://msh-decision-model.md/), in the locked module layout and with the locked exception hierarchy above.

```python
@dataclass(frozen=True)
class PlayerDecision:
    kind: DecisionKind                          # PLAYER, OBJECT, ABILITY, MANA, NUMBER, BOOL, ...
    attrs: frozenset[tuple[str, Hashable]]      # structural facts: ("color", "R"), ("zone", "battlefield")
    modifiers: frozenset[tuple[str, Hashable]]  # refinements: ("spend", "instant_or_sorcery")
    ref: GameRef | None = None                  # provenance; None for pure values

def satisfies(specific: PlayerDecision, general: PlayerDecision) -> bool:
    return specific.kind == general.kind and general.attrs <= specific.attrs
    # modifiers and ref are invisible to satisfies()

@dataclass(frozen=True)
class GameRef:
    player: frozenset[tuple[str, Hashable]] = frozenset()
    zone: frozenset[tuple[str, Hashable]] = frozenset()    # provenance, not stable identity
    card: frozenset[tuple[str, Hashable]] = frozenset()    # printed identity
    object: frozenset[tuple[str, Hashable]] = frozenset()  # instance; carries the opaque engine-minted instance id
    ability: frozenset[tuple[str, Hashable]] = frozenset()
```

Requirements:

- `satisfies()` is a free function, never a method. Decisions and refs are frozen, hashable, serializable.
- **Smart constructors are the schema**: `Decision.mana(color=..., spend=...)`, `Decision.yes()`, `Decision.no()`, `Decision.number(n)`, `Decision.obj(ref, **attrs)`, `Decision.player(ref)`, etc. They are the only sanctioned way to build decisions; they validate attrs against the blessed per-kind schema.
- **Game Symbols vocabulary**: `DecisionKind` is a closed enum; the per-kind attr schema and canonical Modifier names live in one module-level, importable definition (this is the frozen-per-checkpoint vocabulary).
- **Player Query**: `source` (set of Player Decisions), `prompt` (str), `options` (ordered tuple of Player Decisions — implementation-provided stable order is part of the contract), `min`/`max` ints; `min=0` means legally declinable.
- **Ref subset matching**: a helper that matches a ref pattern against a richer ref field-by-field with the same subset rule, for intent routing.
- **Game Refs registry**: engine-owned; mints one opaque instance id per game object (tokens, stack objects, permanents — a zone change yields a new object) and builds `GameRef`s for them. Instance ids are never test-authored.
- **Boundary validation** (`queries.py`): validate every query as raised — unknown kind, malformed attrs (outside the blessed schema), or unstable/empty option order is an explicit, attributable engine failure with its own exception type. These signals replace `ScriptExhaustedError`.
- Unit-test the data layer directly in `engine_tests/` (satisfaction/subsumption, surplus-attr tolerance, modifier invisibility, exact-equality numbers, ref matching, registry id stability and zone-change re-minting).
# Phase 2 — Engine protocol rewrite

Replace the V1 choice surface in `engine/player.py`:

- The `Player` ABC exposes a single entry point — `answer(query: PlayerQuery) -> Answer` — where an answer is a selection of between `min` and `max` of the offered options (plus an explicit decline representation for `min=0`). Delete `choose_target`, `choose`, `choose_yes_no`, `choose_card`, `assign_damage_order`, and `ScriptExhaustedError`.
- Convert **every** engine call site found in Phase 0 to construct a Player Query through the Game Refs registry and the smart constructors: targeting, modal choices, mana color choices, additional/optional cost payment, sacrifice prompts, damage ordering (an ordering query: options = combatants, max = len(options), order of the answer is the assignment order), trigger ordering, replacement-effect choice, discard/mulligan selection — whatever exists in the engine today.
- The engine guarantees **only legal options are offered** (generalizing the existing `TargetRequirement.filter_fn` machinery) and validates restricted decisions at spend time via Modifier-reading predicates (natural home: the `add_restricted` mana primitive).
- The engine routes every query through the boundary validator before handing it to the player.
- Keep the engine deterministic: option order must be stable and derived from game state (e.g. timestamp/zone order), never from set/dict iteration order.
# Phase 3 — DeterministicPlayer (MSH): the intent layer

Rewrite the test player in `engine/intent_player.py` (locked location; the class name stays `DeterministicPlayer`):

- **Lifecycle**: `start_intent(name, intent)` / `end_intent(name)` — postcondition checked at `end_intent`. Multiple intents may be active simultaneously.
- **Routing**: each query is routed to an active Intent by pattern-matching its `source` refs (subset rule per ref field). Two active intents matching one query = hard test-authoring error (raise immediately). Card identity is statically writable; only opaque instance ids are bound dynamically.
- **Answering**: preference-based — scan options in the implementation-provided order, take the first option that satisfies a preferred decision and is valid; greedy single pass, no search. Exact equality for numbers.
- **Baseline Intent**: an always-active default handler for system-level queries (trigger ordering, replacement defaults). Card intents take precedence. A query matched by neither card intent nor baseline = explicit failure.
- **Query transcript**: the player (or a harness hook) logs every query raised — source, options, min/max, answer — for option-set invariant assertions.
- Rewrite `test_utils.py` / `test_utils.md` around this API (board setup helpers survive; the directive queue for actions survives as the action channel; the choice script dies). Update `workspace/AGENTS.md` and `PROJECT_MAP.md` to describe the new API and remove all `sos` references.
- Canonical test shape (illustrative — exact helper names come from your `test_utils.py` rewrite; the pattern is binding, the identifiers are not):
```python
def test_strike_kills_bear(game, p0, p1):
    bear = put_on_battlefield(p1, "fdn_215")                       # board setup helpers survive
    p0.start_intent("strike", Intent(
        pattern=GameRef(card=frozenset({("number", "fdn_123")})),  # routes queries raised by this card
        preferences=(Decision.obj(("instance", bear.instance_id)),),
        postcondition=lambda g: g.zone_of(bear) == "graveyard",
    ))
    cast_spell(p0, "fdn_123")                                      # action channel: directive, unchanged
    resolve_stack(game)
    p0.end_intent("strike")                                        # postcondition checked here
    # option-set invariant: the engine never offered an illegal target
    offered = p0.transcript.queries(kind=DecisionKind.OBJECT)[-1].options
    assert not any(("keyword", "hexproof") in opt.attrs for opt in offered)
```

# Phase 4 — Migrate FDN implementations and reference tests

- Convert every `cards/fdn/{cn}/card_impl.py` to the new protocol: wherever an implementation called `player.choose_*` directly or constructed V1 choice flows, it now raises Player Queries via the engine's query machinery with proper refs and Modifiers.
- Rewrite every colocated `cards/fdn/{cn}/tests.py` (FDN Reference Tests — agent-visible learning material) in the intent style: `start_intent` / actions / `end_intent`, preferences over Player Decisions, postconditions, and at least one option-set invariant example. These files teach future agents the pattern — make them exemplary, not minimal.
- The fdn_81 private-attribute pokes (`_resolve_targets`, `_damage_assignments`) noted in V1 known issues must not survive migration — express them as queries/intents.
- All migrated FDN reference tests must pass against the migrated engine.
# Phase 5 — engine_tests/ migration

- Update `engine_tests/` to the new protocol in the same change series.
- Any V1 regression coverage that cannot be re-expressed under the new protocol must be **explicitly logged** (file path + test name + reason) in a `DROPPED_COVERAGE.md` next to `engine_tests/` — never silently dropped.
- Add new protocol-level suites: boundary validation failures, ambiguous-intent hard error, baseline-intent fallthrough, decline semantics (`min=0`), ordering queries.
# Phase 6 — FDN replay validation on the new engine

Adapt `silverquillm/replay/` so the FDN replay corpus validates the MSH engine + migrated FDN impls. The pipeline (raw JSON → `parse_replay()` → `ReplayGame` → `ReplayExecutor`/`ValidatingExecutor` → `ValidationReport`) and the dual-seat observer model are unchanged; what changes is how the executor drives the engine:

- **Benchmark-parameterized engine target**: the replay CLI/executor must select which workspace engine it imports (SOS frozen path vs `benchmarks/msh/workspace/engine/`) — e.g. a `--benchmark` flag resolving via `benchmarks/*/config.json`. SOS replay validation must keep working against the SOS engine unchanged.
- **Intent-driven seat 1**: instead of feeding scripted `choose_*` answers, the executor instantiates the intent-based `DeterministicPlayer` and derives intents from the GRE stream: for each seat-1 action window, mint an intent whose preferences are Player Decisions constructed from the known outcome in the next snapshot (chosen targets, chosen colors, ordered triggers), and whose postcondition is the relevant slice of the next GRE state.
- **Object correlation**: maintain a GRE `objectId`/`instanceId` ↔ engine instance-id correlation map (extend `ObjectTracker`) so replay-derived preferences can reference engine-minted ids. This is the dynamic-binding path the spec reserves for instance ids.
- **Baseline Intent for system queries**: trigger ordering and default choices follow GRE-observed order via the executor's baseline intent.
- **Seat 2 oracle injection** stays as is.
- **New divergence types**: extend `DivergenceType` with at least `QUERY_UNANSWERED` (no replay-derived intent matched a raised query) and `PROTOCOL_ERROR` (boundary validation failure). An unanswerable query is a recorded divergence, never a crash of the validation run.
- Regenerate/extend the card ID map if needed (`scripts/build_card_id_map.py`).
**Parity bar**: run the same FDN corpus as the Phase 0 baseline. Per-file divergence counts must be ≤ the V1 baseline; every new divergence must be triaged in the report as (a) migration bug — fix it, or (b) pre-existing engine gap now surfaced more precisely — document it.

**Triage procedure (follow mechanically, per new divergence)**:

1. Look up the same replay file and step in the Phase 0 baseline report. If an equivalent divergence exists there, classify as (b) pre-existing: document and move on. Do not fix pre-existing engine gaps in this task.
2. Otherwise classify as (a) migration bug. Reproduce it as a minimal engine/intent test first, then fix. Maximum 3 fix attempts per divergence; if still failing, record it in the report under an `unresolved` section with the failing step, the query-transcript slice, and your best hypothesis — then continue. Do not spin.
3. Never make a replay pass by editing replay JSON, hand-editing the card ID map, weakening `satisfies()`, or loosening boundary validation.
# Common failure modes — hard DO NOTs

- Do **not** write a "temporary" adapter that maps Player Queries back to `choose_*` calls — not even as a Phase 2 stepping stone. Convert call sites directly.
- Do **not** derive option order from `set`/`dict` iteration. Sort by a stable game-state key (timestamp, then zone index) and record the chosen key in `KEY_DECISIONS.md`.
- Do **not** make `satisfies()` a method, add modifiers or ref to its comparison, or special-case any kind inside it.
- Do **not** let intents inspect or mutate game state to decide answers — preferences are declared up front; the only dynamic binding is engine-minted instance ids.
- Do **not** catch `ProtocolError` subclasses inside the engine to "keep going" — they must surface.
- Do **not** weaken or delete a failing test to get green. Either fix the code or log the test in `DROPPED_COVERAGE.md` with a reason.
- Do **not** touch anything under `benchmarks/sos/`, even if a shared change appears to break SOS — if that happens, your shared change is wrong; redesign it. The replay layer is the only shared code you may modify, and only in benchmark-parameterized ways.
- Do **not** rename glossary terms or the `DeterministicPlayer` class.
- Do **not** start Phase 4 while any engine call site from the Phase 0 checklist remains unconverted.
# If you get stuck

- Blocked on spec interpretation: re-read `MSH-DECISION-MODEL.md` first — the spec wins. If genuinely ambiguous, pick the simplest reading consistent with the glossary, implement it, and log the ambiguity and your choice in `KEY_DECISIONS.md`.
- Blocked on a failing test or divergence: 3-attempt cap, then document and move on (see the Phase 6 triage procedure — apply the same cap everywhere).
- Blocked on missing context (a file this prompt names does not exist, or an API has drifted): trust the repo over this prompt for mechanical details, trust the spec over both for semantics, and log the discrepancy.
- Never resolve a blocker by expanding scope (touching SOS, the repo-level `tests/` harness, or MSH card content).
# Final self-check (run verbatim before declaring done)

```bash
pytest benchmarks/msh/workspace/engine_tests/ -q
pytest benchmarks/msh/workspace/cards/fdn/ -q
grep -rn "choose_target\|choose_yes_no\|choose_card\|assign_damage_order\|ScriptExhaustedError" benchmarks/msh/workspace/
git diff --stat origin/main -- benchmarks/sos/
# plus: the replay validate CLI on the FDN corpus against the MSH engine target,
# and once against the SOS target to confirm SOS replay validation is unchanged
```

Then restate the seven acceptance criteria in your final summary and confirm each one explicitly, with evidence.

# Acceptance criteria (all must hold)

1. `grep -rn "choose_target\|choose_yes_no\|choose_card\|assign_damage_order\|ScriptExhaustedError" benchmarks/msh/workspace/` returns nothing (modulo the dropped-coverage log and historical docs).
2. `engine_tests/` green; `DROPPED_COVERAGE.md` present (possibly empty) and every dropped test justified.
3. All FDN reference tests green against the migrated engine and impls.
4. FDN replay validation runs end-to-end on the MSH engine via the intent-based DeterministicPlayer and meets the parity bar; report committed.
5. SOS untouched: `git diff --stat` shows zero changes under `benchmarks/sos/`; SOS replay validation and the repo-level platform/validation test suites still pass.
6. Workspace docs (`AGENTS.md`, `PROJECT_MAP.md`, `test_utils.md`) describe only the new API; no V1 two-channel documentation survives.
7. `KEY_DECISIONS.md` contains entries for every micro-decision made (module layout, answer/decline representation, ordering-query shape, divergence-type additions, etc.).
# Out of scope

- Anything under `benchmarks/sos/` or the SOS conformance checker.
- MSH card implementations, MSH oracles, MSH audited tests, and the MSH conformance rule-set (subsequent tasks).
- The repo-level `tests/` harness generalization (separate task; do not block on it).
- Checkpoint mechanics ([MSH-CHECKPOINTS.md](http://msh-checkpoints.md/)) beyond keeping decisions/refs serializable.
