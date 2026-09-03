Status: DRAFT

Last updated: 2026-06-10

# V2 Player Choice / Decision Model

A standardized, testable shape for arbitrary player choices: engines raise Player Queries; audited tests answer them through Intents choosing among Player Decisions. Engine-level and pool-neutral (renamed from MSH-DECISION-MODEL.md at grilling 2026-08-27); it now governs the V2 engine carried into the HOB-generation benchmarks.

## Context

In V1 choices were answered positionally (a flat FIFO script), so one audited test could not fairly score the many valid ways to implement a choice — "add one mana of any color" alone had 20+ incompatible implementations. Two goals in tension: minimal engine enforcement (primitives, not per-card decision logic) and accepting any implementation that produces the correct observable outcome. The query protocol is the V2 engine's native interaction surface (no V1 adapter); the intent layer serves audited tests only, and the engine itself stays deterministic and imperative.

## Design

### Vocabulary (canonical terms — see [CONTEXT.md](../../CONTEXT.md))

| Term | Meaning |
| --- | --- |
| Game Symbols | Immutable benchmark-owned vocabulary of Player Decision kinds and attr values. Closed. |
| Game Refs | Dynamic extension of Game Symbols to all actual game objects (tokens, stack objects), tracked by the engine. |
| Player Decision | Immutable struct: one unit of choice (kind + attrs + Modifiers + optional Game Ref). |
| Player Query | A question raised to a player: source, prompt, ordered options, min/max. |
| Modifiers | Refinements riding on a Player Decision; invisible to matching; agent-expandable. |
| Intent | Test-scoped query handler with explicit lifecycle and postcondition. |

### Player Decision

```python
@dataclass(frozen=True)
class PlayerDecision:
    kind: DecisionKind                          # PLAYER, OBJECT, ABILITY, MANA, NUMBER, BOOL, ...
    attrs: frozenset[tuple[str, Hashable]]      # structural facts: ("color", "R"), ("zone", "battlefield")
    modifiers: frozenset[tuple[str, Hashable]]  # refinements: ("spend", "instant_or_sorcery"), ("snow", True)
    ref: GameRef | None = None                  # provenance; None for pure values (yes/no, numbers, colors)

def satisfies(specific: PlayerDecision, general: PlayerDecision) -> bool:
    return specific.kind == general.kind and general.attrs <= specific.attrs
    # modifiers and ref are invisible to satisfies()
```

- Pure data with zero behavior; `satisfies()` is a free harness function, never a method. Subsumption is a relation, not inheritance; structural matching survives cross-engine class identity; frozen structs serialize for checkpoints and give stable ordering; no method body exists for per-card logic to leak into.
- One flat struct + smart constructors (`Decision.mana(color=R, spend=INSTANT_SORCERY)`, `Decision.yes()`, `Decision.number(3)`) — the constructors are the schema; no per-kind tagged union, no subclasses.
- attrs = what the choice is (intents constrain on these). Modifiers = refinements (read only by engine predicates and audit assertions). The split makes "an intent that accidentally requires a restriction" unrepresentable.
- Number satisfaction is exact equality — no range or predicate matching.
### Game Ref

```python
@dataclass(frozen=True)
class GameRef:
    player: frozenset[tuple[str, Hashable]] = frozenset()
    zone: frozenset[tuple[str, Hashable]] = frozenset()    # zone as of the query — provenance, not stable identity
    card: frozenset[tuple[str, Hashable]] = frozenset()    # printed identity: static, test-author-knowable
    object: frozenset[tuple[str, Hashable]] = frozenset()  # the instance; carries an opaque engine-minted instance id
    ability: frozenset[tuple[str, Hashable]] = frozenset()
```

- Hierarchical provenance; any field may be empty. Each field is a mini attr-set in the Game Symbols vocabulary, so the single subset-matching primitive is reused per field.
- Role split: refs for intent (routing, cross-query correlation), attrs for choice (preferences, invariants, `satisfies()` — which stays ref-blind). Overlap is allowed (e.g. choose-target-player); extra attrs are ignored — the player best-guesses what the query is about, then chooses by preference.
- `card` vs `object`: printed identity vs instance. The instance id is the only opaque engine-minted piece — never hardcoded, bound dynamically at action time, needed only to disambiguate identical instances. A zone change yields a new object.
- **Stint-based minting**: the Game Refs registry mints instance ids lazily — on first observation of an object during a zone stint — and `move_to_zone` notifies the registry on every zone change (`note_zone_change`), breaking id continuity even when the new stint is never observed by a query (e.g. a flicker's exile leg). Observation-only tracking is rejected: it silently reuses a stale id across an unobserved round-trip. Low-level container moves bypass the hook, so card code must route every game-visible zone change through `move_to_zone`.
- Pure-value decisions (yes/no, numbers, colors) carry no ref; the query's source decisions carry the refs.
### Player Query

| Field | Type | Meaning |
| --- | --- | --- |
| source | set of Player Decisions | what raised it — routing matches on source refs |
| prompt | string | human-readable description |
| options | ordered tuple of Player Decisions | the legal choices; implementation-provided stable order is part of the contract |
| min / max | int | how many must / may be chosen; `min=0` = legally declinable |

### Extension policy

- **Kinds: closed.** Fixed enum owned by the benchmark, frozen per checkpoint; adding one is a benchmark-version event.
- **attrs: closed but surplus-tolerant.** Intents and oracles use only the blessed per-kind schema (defined by the smart constructors); engines may attach extra attrs — inert for matching.
- **Modifiers: open but canonical-when-audited.** Engines may invent private Modifiers freely; any Modifier an audited test asserts on must use the canonical name.
### Boundary validation

Validation is engine-side: the query layer validates every query as it is raised — an option with an unknown kind or malformed attrs, or an unstable/empty option order, is an explicit, attributable engine failure (the `ProtocolError` family) — distinct from "no offered option satisfies the intent" (the `IntentError` family, attributable to the test). These two signal families replace `ScriptExhaustedError`.

Fault attribution requires propagation: card implementations must never catch exceptions raised by the query helpers (`choose_*` / `query_*`) — an `except Exception` wrapper silently converts a protocol or intent fault into a wrong game action (an unanswerable query becoming a default choice). Guards are legitimate only around APIs that signal failure by return value (e.g. `mana_pool.pay()` returns `False`, never raises).

### Concrete protocol surface (locked 2026-06-10)

Locked alongside the Task #1 implementation prompt; recorded here so the spec, not the prompt, is canonical.

**Module layout** — `engine/decisions.py` (kinds, decisions, refs, `satisfies()`, the Game Symbols vocabulary, exceptions), `engine/queries.py` (`PlayerQuery`, `Answer`, boundary validation), `engine/refs_registry.py` (Game Refs registry), `engine/player.py` (the `Player` ABC with the single entry point `answer(query) -> Answer`), `engine/intent_player.py` (`Intent`, `DeterministicPlayer`, query transcript).

**Exception hierarchy** — engine-fault vs test-fault split:

```python
class ProtocolError(Exception): ...            # engine-side protocol failure
class UnknownKindError(ProtocolError): ...
class MalformedAttrsError(ProtocolError): ...
class InvalidOptionsError(ProtocolError): ...  # empty options with min > 0, malformed option, unstable order

class IntentError(Exception): ...              # test-authoring failure
class AmbiguousIntentError(IntentError): ...
class UnmatchedQueryError(IntentError): ...
class InvalidAnswerError(IntentError): ...     # answer violates min/max or options membership
class PostconditionError(IntentError): ...
```

**Answer / decline** — `Answer(selected: tuple[PlayerDecision, ...])`: each element equals one of `query.options`, no duplicates, `min <= len(selected) <= max`, validated by the engine before applying. Decline is `Answer(selected=())`, legal iff `min == 0`; there is no separate Decline type.

**Ordering queries** — `min == max == len(options)`; the order of `Answer.selected` is the assignment order (damage assignment, trigger ordering).

**Intent shape** — frozen dataclass: `pattern: GameRef` (matched against query source refs, subset rule per field), `preferences: tuple[PlayerDecision, ...]` (scanned in order; first satisfied and offered option wins), optional `postcondition` (checked at `end_intent`). The registry name is passed to `start_intent(name, intent)`, not stored on the Intent.

**Baseline Intent slot** — a regular Intent with an empty pattern held in a dedicated slot on the player, consulted only when no card intent matches; at most one set at a time.

### Implementation sequencing and V1 migration

The query/decision/intent layer is the MSH workspace's task #1 (grilling 2026-06-10): Player Query, Player Decision, and Intent land before any MSH oracle test is authored. Player Query is a native engine protocol with no V1 adapter — boundary validation requires engine-side option structure an adapter cannot provide, so the MSH engine mints instance ids, owns the Game Refs registry, and routes every player interaction through structured queries. The duplicated V1 two-channel `test_utils` / `DeterministicPlayer` are deleted, not deprecated (zero MSH tests depend on them yet, so the migration is free); `engine_tests/` are updated in the same change series, and any V1 regression coverage that cannot be re-expressed is explicitly logged, never silently dropped.

The MSH player keeps the name `DeterministicPlayer` (grilling 2026-06-10): benchmark-scoped glossary entries in [CONTEXT.md](../../CONTEXT.md) (`DeterministicPlayer (SOS)` vs `DeterministicPlayer (MSH)`) disambiguate it from the frozen V1 two-channel player, and the classes live in per-benchmark workspaces that never import each other.

### Intent-driven answering (audited tests only)

- **Lifecycle**: `start_intent(player, name)` → imperative actions → `end_intent(player, name)`, where the postcondition is checked. Multiple intents may be active; intent status is driven by the test.
- **Subset-asking**: the DeterministicPlayer accepts a range of potential queries per intent; a valid engine may ask any subset, in any order or decomposition (three small prompts, one combined prompt, or only the final choice).
- **Answering is preference-based**: the named intent is the scoping/lifecycle layer; answers come from preferences over Player Decisions, which generalize across decompositions (declining "none" on a sacrifice query must cohere with answering "no" to a yes/no offer).
- **Determinism**: the player scans the implementation-ordered options and takes the first option that is both intended (satisfies a preferred decision) and valid. Greedy, single pass, no search; the postcondition then asserts the goal actually held.
- **Preference misses are transcript data, not errors**: when a card intent matches a query but none of its preferences match any offered option (and `min > 0`), the player still answers deterministically (first valid option) and flags `preference_miss` on the transcript record. The exception hierarchy stays locked; audited tests that need a miss to be a failure assert it over the query transcript.
- **Routing**: queries route to intents by pattern-matching on structured source refs; most patterns are statically writable (card identity is known a priori). Dynamic binding is reserved for opaque instance ids. An ambiguous match is a hard test-authoring error.
- **Baseline Intent**: always-active defaults for system-level query patterns (trigger ordering, replacement choice); card intents take precedence; a query matched by neither is an explicit failure. The baseline is part of the frozen benchmark contract.
### Rigor (three independent layers)

1. **Option-set invariants over the query transcript** — the harness logs every query raised (source, options, min/max, answer); tests assert pattern-based invariants over the log (e.g. every creature offered to sacrifice has controller = player0). Decomposition-robust; catches engines that offer illegal options even when the intent never picks one.
2. **Postconditions** checked at `end_intent`.
3. **Intent spreads as suite design**: each audited test asserts a single must-achieve intent; optionality is covered by separate tests per option (one test per color for "any color", plus a decline test where legal), including negative/impossible intents that must fail cleanly.
### Minimal engine enforcement

Two things legitimately remain engine-side:

1. Computing the legal option set (generalizes the existing `TargetRequirement.filter_fn`).
2. The spend-time predicate for restricted decisions (natural home: the existing `add_restricted` primitive).
The engine guarantees only legal options are offered and restricted decisions are validated at use; the test, via intent, only ever picks among already-legal options.

### Worked example — "Add one mana of any color" (V1: sos_257)

For "T, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.":

- **Query**: source = the land's decisions; options = five MANA decisions (W, U, B, R, G), each carrying the `spend: instant_or_sorcery` Modifier; min = max = 1.
- **Intent**: preference = the general RED mana decision; postcondition = pool gains a red mana. The player picks the offered restricted-red because it satisfies RED (extra Modifiers never block matching). The Modifier is the spend restriction.
- **Suite spread**: one test per color (each must succeed — proves genuinely any-color), plus a spend-time check that the restricted mana cannot pay for a creature.
