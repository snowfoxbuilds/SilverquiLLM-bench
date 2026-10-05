Status: DRAFT

Last updated: 2026-10-06

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
| question | tuple of canonical objects | an optional annotation of what the query asks for; empty when the engine attaches none |

The question payload is an optional contextual annotation that helps a player tell what a question asks when several valid questions are possible in one situation, such as `CardType.ARTIFACT` on "choose an artifact card" when an effect asks for a card of each type in turn (grilling 2026-10-04).
Engines need not attach it, and tests read it best-effort.
Its values must be canonical — the engine's Game Symbols, predefined classes, Game Refs, or Player Decisions built from them; a raw string or a custom symbol is a protocol error, rejected when the query is raised (grilling 2026-10-04).
A test names what a query asks for with the same objects and matches them as preferences match options: a Player Decision by `satisfies()`, any other object by identity or equality.

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

class InvalidPlayerChoiceError(Exception): ... # fra-hard-v2 onward: the engine rejects a chosen option as illegal under the rules
class PostconditionError(IntentError): ...
```

**Answer / decline** — `Answer(selected: tuple[PlayerDecision, ...])`: each element equals one of `query.options`, no duplicates, `min <= len(selected) <= max`, validated by the engine before applying. Decline is `Answer(selected=())`, legal iff `min == 0`; there is no separate Decline type.

**Ordering queries** — `min == max == len(options)`; the order of `Answer.selected` is the assignment order (damage assignment, trigger ordering).

**Intent shape** — frozen dataclass: `pattern: GameRef` (matched against query source refs, subset rule per field), `preferences: tuple[PlayerDecision, ...]` (in rank order; each takes the first offered option that satisfies it), optional `postcondition` (checked at `end_intent`). The registry name is passed to `start_intent(name, intent)`, not stored on the Intent.

**Baseline Intent slot** — a regular Intent with an empty pattern held in a dedicated slot on the player, consulted only when no card intent matches; at most one set at a time.

### Implementation sequencing and V1 migration

The query/decision/intent layer is the MSH workspace's task #1 (grilling 2026-06-10): Player Query, Player Decision, and Intent land before any MSH oracle test is authored. Player Query is a native engine protocol with no V1 adapter — boundary validation requires engine-side option structure an adapter cannot provide, so the MSH engine mints instance ids, owns the Game Refs registry, and routes every player interaction through structured queries. The duplicated V1 two-channel `test_utils` / `DeterministicPlayer` are deleted, not deprecated (zero MSH tests depend on them yet, so the migration is free); `engine_tests/` are updated in the same change series, and any V1 regression coverage that cannot be re-expressed is explicitly logged, never silently dropped.

The MSH player keeps the name `DeterministicPlayer` (grilling 2026-06-10): benchmark-scoped glossary entries in [CONTEXT.md](../../CONTEXT.md) (`DeterministicPlayer (SOS)` vs `DeterministicPlayer (MSH)`) disambiguate it from the frozen V1 two-channel player, and the classes live in per-benchmark workspaces that never import each other.

### Intent-driven answering (HOB benchmarks)

From fra-hard-v2 onward, Audited Tests answer every query from the players' scripts instead, with no Intents or Baseline Intent ([Test Interface](TEST-INTERFACE.md), grilling 2026-10-05).


- **Lifecycle**: `start_intent(player, name)` → imperative actions → `end_intent(player, name)`, where the postcondition is checked. Multiple intents may be active; intent status is driven by the test.
- **Subset-asking**: the DeterministicPlayer accepts a range of potential queries per intent; a valid engine may ask any subset, in any order or decomposition (three small prompts, one combined prompt, or only the final choice).
- **Answering is preference-based**: the named intent is the scoping/lifecycle layer; answers come from preferences over Player Decisions, which generalize across decompositions (declining "none" on a sacrifice query must cohere with answering "no" to a yes/no offer).
- **Determinism**: selection is preference-major — each preference in rank order takes the first remaining offered option, in the implementation's order, that satisfies it, until `max` is reached, and a mandatory query is then filled to `min` in option order (grilling 2026-10-05). Greedy, single pass, no search; the postcondition then asserts the goal actually held.
- **Preference misses are transcript data, not errors**: when a card intent matches a query but none of its preferences match any offered option (and `min > 0`), the player still answers deterministically (first valid option) and flags `preference_miss` on the transcript record. The exception hierarchy stays locked; audited tests that need a miss to be a failure assert it over the query transcript.
- **Routing**: queries route to intents by pattern-matching on structured source refs; most patterns are statically writable (card identity is known a priori). Dynamic binding is reserved for opaque instance ids. An ambiguous match is a hard test-authoring error.
- **Baseline Intent**: always-active defaults for system-level query patterns (trigger ordering, replacement choice); card intents take precedence; a query matched by neither is an explicit failure. The baseline is part of the frozen benchmark contract.
### Priority actions (fra-hard-v2 onward)

When a player receives priority, the engine raises a Priority Query offering that player's available actions.
Audited Tests choose one through their scripts, and the engine turns the chosen action into its own casting or activation call (grilling 2026-10-03).
The Priority Query is how the game runs, not a test hook: it corresponds to the set of choices a user interface would offer a real player at that moment (grilling 2026-10-04).
This applies to the Known-Best Engine, smoke, fra-hard-v2 and later benchmarks; fra-hard v1, the HOB tiers and SOS keep directive-driven priority.

#### Options

- **Option shape**: no new Decision kind.
  Casting a spell or playing a land is an OBJECT option for the object cast or played; activating an ability, mana abilities included, is an ABILITY option.
  Passing priority is a decline (`min=0`), and an X value stays a NUMBER choice made during casting (grilling 2026-10-04).
- **Recognizing the query**: a Priority Query's one source is the PLAYER decision for the player receiving priority, whose ref carries that player's seat and the `("window", "priority")` entry in its `ability` field.
  `priority_pattern(seat)` is the Intent pattern that matches it; a card intent patterned on card identity never does.
- **Settling first**: before each Priority Query the game is settled — continuous effects re-derived and state-based actions performed — including after an action that paid a cost or left the stack empty (CR 117.5).
- **What is offered**: every action the player may begin under timing, zone and cast-permission rules; costs and targets are not pre-checked (grilling 2026-10-04).
  Card conditions that depend on targets or other casting-time checks are not pre-checked either, so such a spell is offered and its cast rejected.
  A "cast it from your graveyard this turn" permission is offered only to the player it was granted to, only while the card stays in the graveyard as the object it named (CR 400.7), and ends at the next cleanup step, as "this turn" effects do (CR 514.2), so a priority window that cleanup opens no longer offers it; a permission granted in that window lasts until the next cleanup iteration.
  The timing of a multi-face card is judged by the face being cast (CR 715.3a), so the card, not the engine's generic timing check, decides which of its faces may begin casting, and an instant face of a creature card is offered at instant speed.
- **Combat declarations**: declaring attackers and declaring blockers are Player Queries too — a multi-select of OBJECT options for the creatures that could attack or block, with whom each attacks or blocks.
  They replace the imperative `declare_attackers` / `declare_blockers` calls and the convention that the engine silently filters illegal attackers and blockers (grilling 2026-10-04).
- **Multi-face cards**: the benchmark predefines no face structure — Glamdring, Foe-hammer is one object and Gleam of Death another, and the candidate decides how they relate (grilling 2026-10-04).
  Any Player Query that can present such a card — a Priority Query, a target or graveyard selection such as Uldaros's, an effect-granted cast — may offer it as one object or as one object per face.
  Within one priority, Gleam of Death may be offered at once and chosen in one query, or Glamdring may be chosen first and a second query then asks Glamdring or Gleam of Death.
  A test's ordered preferences (Gleam of Death, otherwise Glamdring) answer either, and the test judges the outcome: the intended face on the stack (grilling 2026-10-04).

#### Printed identity

- **Predefined classes**: every card, every face of a multi-face card, and every printed ability has its own predefined class in the Workspace, such as `GlamdringFoehammer` and `GleamOfDeath` for an Adventure card, or `EmrakulTheExigentDoomAbility1` for "When you cast this spell, untap all lands you control."
  Each printed line is one ability, except that keywords sharing a line are separate abilities ("Flying, trample" is two); abilities, modes included, are numbered in printed order, so Emrakul's Flying is `EmrakulTheExigentDoomAbility2` and its trample `EmrakulTheExigentDoomAbility3`.
  Face classes subclass the engine's card type class and ability classes are plain classes carrying their printed text; nothing links them, and how they relate is the candidate's design.
  The classes are generated from each Card Spec's printed text into the card's `card_impl.py`, for every card in the Workspace, FDN included — first in the Known-Best Workspace, then ported to fra-hard-v2 (grilling 2026-10-04).
- **`printed` attr**: OBJECT, ABILITY and MODE decisions carry a blessed `printed` attr whose value is the predefined class the option stands for, and tests match on it (`Decision.obj(printed=GleamOfDeath)`).
  An instance id identifies one object in play, but implementations differ in which objects they present for a face; `printed` picks the intended choice in any valid implementation, and instance ids remain only to tell identical objects apart.
  A copy carries the class of what it copies (grilling 2026-10-04).
- **No raw strings**: tests place, choose and assert by predefined classes, never by a name string.
  Game Symbols values stay a closed, validated vocabulary exposed as named constants (grilling 2026-10-04).

#### Legality

- **Offering is legal, allowing is not**: an engine may present and let the player choose an illegal option; it must then reject it by raising `InvalidPlayerChoiceError` and roll the game back to the start of the rejected action.
  An engine that never presents illegal choices never needs the error.
  A test fails only when an illegal choice is allowed to take effect and play proceeds to the next priority (grilling 2026-10-04).
- **Rejection boundary**: the start of the rejected action is the beginning of the Priority Query in which an ordinary priority action began, the beginning of the declaration for a combat declaration, and, for an effect-granted cast or another choice made while an object resolves, the point just before that cast or choice.
  A rollback never reverses what came before that boundary: a resolving Uldaros keeps its exiled cards, its copies and any copy already cast when a later copy's cast is rejected, as CR 733 reverses only the illegal action (grilling 2026-10-04).
  The engine then asks the same query again and play continues from it; a rejected attempt consumes no further action-script entry.
  `InvalidPlayerChoiceError` is a rules rejection, distinct from the ProtocolError and IntentError families, which report malformed queries and test-authoring faults.
- **Rejection scenarios**: implementation tests check, after each rejection, that the state at the boundary is restored, that effects before it stand, and that play continues without consuming another script entry — for a failed ordinary cast followed by a legal cast, a rejected later Uldaros copy after an earlier copy was cast, and an illegal combat declaration followed by a legal one.
- **Owning a rejection**: each priority action, resolution, and cast or choice made while an object resolves is an attempt, and a rejection belongs to one answer given during it.
  A choice the card or engine refuses belongs to the attempt's latest answer; an action the rules forbid as a whole (a casting, activation or zone-move error) belongs to the answer that chose the action.
  Only that answer's player hears the error, through `Player.on_attempt_rejected`, after the rollback, and answers retry, pass, or raises to stop play; the default raises for anything but a priority action, which it hands to `Player.on_choice_rejected`.
  A rejection its owner raises, or one no answer owns, is final: the attempt has already rolled back to its own boundary, so the error passes every enclosing attempt without another rollback or notification, keeping what those attempts completed before it, and reaches the caller unchanged.
  Every Player hears rejections this way, whatever its preferences; state it keeps for its decisions is listed in its `rollback_exempt`, since a retry rolls the game back again — to the same boundary, after every hook has returned, for a priority action as for a resolution or explicit attempt.
  When the rejected choice inside a priority action is not the action itself — another player's choice, or a choice Intent's — the acting player hears `Player.on_action_retried` and chooses the same action again.
  Decision-side state — a player's intents, transcript, script position and attempt bookkeeping — is not game state, and the rollback leaves it alone.
- **Retrying a rejected choice**: a retry is never inferred; each test writes out every way it may be retried (grilling 2026-10-04).
  A script entry or choice Intent holds ordered branches, each an ordinary preference list that answers every query of an attempt, and the handler that owns the rejected answer — the entry, or the choice Intent that answered — retries the attempt with its next branch.
  A handler with one preference list has one branch, so its rejection fails the test, and one that runs out of branches fails the same way.
  Because each branch answers every query of the attempt, the retry does not depend on how the engine presented the choice: with branches [Gleam of Death, Glamdring] then [Glamdring] and Gleam of Death illegal, an engine that offers Gleam of Death at once casts Glamdring on the retry, and so does one that asked Glamdring and then Gleam of Death (grilling 2026-10-04).
  A choice Intent's rejection while an entry's action is cast leaves the entry's action and branch as they were and retries the choice with the Intent's next branch.
  Choice branches belong to one action: when a script entry is consumed — including a successor that takes over a window an expected-illegal entry handed on — every handler's choices, the opponent's and the baseline's included, start again from their first branch, while a retry of the same entry keeps where they had reached.
  Inside its action the entry answers every query that no choice Intent claims and no baseline preference picks, mandatory fills included, so it owns those answers and a refusal of any of them moves the entry to its next branch; once the action is over — taken, abandoned or ended by an error — the entry answers nothing more.
- **Resolution-time choices**: a choice raised while an object resolves, or while casting outside a Priority Query action, rolls back to its own rejection boundary — just before that cast or choice asked its first query — and is re-asked with the owning Intent's next branch; each such attempt starts again from the Intent's first branch.
  It never re-asks the Priority Query before it, which would replay the passes and resolve the object again (grilling 2026-10-04).
  What a resolution or explicit attempt runs outside the game — its callable and the popped StackObject, such as a spell copy that occupies no zone — is rolled back with the game.
  A resolution is one attempt whose boundary is its first query: a retry runs the effect again from the state before it, and an abandoned choice ends the effect there, keeping the effects that came before, while the object still finishes resolving — a spell leaves the stack for its usual destination, or exile after a flashback cast, unless its effect already moved it.
  Card code that makes several casts or choices while resolving, such as Uldaros's copies, runs each as its own attempt, so a rejected later one keeps the earlier ones and the resolution goes on without it.
  The normal priority loop and the test helpers resolve through the same engine attempt.
- **Testing choices whose presentation varies**: tests never dictate how an engine presents a choice; they are built to draw out the intended choice and to fail when an illegal one takes effect.
  Uldaros's targets are up to one card of each card type, judged by the graveyard characteristics of each card: the chosen cards must be distinct cards that can be assigned to distinct card types they have, though their type sets may overlap.
  Glamdring in the graveyard is an artifact card, never a sorcery (CR 715.4), whatever object an engine presents for it, so with Divination, Glamdring and Leyline Axe in the graveyard an engine fails if it lets all three be exiled; Divination with either artifact is legal.
  Choosing which face to cast happens later and separately, when a copy is cast (CR 715.3a): with Divination and Glamdring exiled, casting only the copy as Gleam of Death (mana value 4) and declining Divination stays within the budget of 6.
  Presentation varies only how questions are asked and answered, never what happens: a test's branches and per-question preferences are written so that every presentation converges on the same outcome, and the test expects that one outcome, never alternatives (grilling 2026-10-05).
- **Uldaros acceptance cases**: two artifact creatures fill the artifact and creature slots; one card is never chosen twice, so a single multi-type card is exiled and copied once — the suite may first repeat a card to probe the engine, falling back to a `distinct` branch when the repeat is rejected, so it converges under every presentation (grilling 2026-10-05); two cards that are only sorceries are never both chosen; and a copy's face is chosen while it is cast, whether the engine offers the faces in one query or across two.

#### Turn structure

- **Entries**: each player has an ordered script of action entries, and each Priority Query or combat declaration the player receives consumes the next one.
  An entry is one action and answers every query within it (choosing Glamdring and then Gleam of Death, or Gleam of Death at once); its goal is checked when the action completes (grilling 2026-10-04).
- **Positive and expected-illegal entries**: a positive entry (`act`) fails the test with `PostconditionError` if no branch's action is offered, if a rejection with `InvalidPlayerChoiceError` leaves it no branch to retry with, or if it misses its goal (grilling 2026-10-04).
  A branch whose action is not offered is skipped, so the entry is "not offered" only when no branch can start.
  An expected-illegal entry (`act_illegal`, the successor to SOS `perform_illegal_action`) tries each of its branches the same way: it passes if every branch is not offered or is rejected, and fails if any takes effect and play reaches the next Priority Query (grilling 2026-10-04).
  A rejection inside an expected-illegal branch's action settles that branch for the acting player before anyone else hears it (`Player.settle_rejected_action`), whoever answered the refused choice: the entry tries its next branch, or hands the same Priority Query to the next entry, without passing priority.
  The exception is a refused choice whose owner would retry it with another branch (`Player.would_retry`), since the action may then still take effect — and if it does, the entry fails.
- **Per-question preferences**: a branch may map keys to the preferences that answer a query a key matches, `branch(A, B, per_query={CardType.ARTIFACT: [A], CardType.CREATURE: [B]})`, on any query — a Priority Query, a combat declaration, or a choice while casting or resolving (grilling 2026-10-04).
  A key is an object the query's question payload holds, matched as above, or any predicate over the query — its payload, offered options, source or bounds — so a test can infer the question best-effort when the engine attaches no payload; keys are tried in mapping order and the first match wins, so several matching keys are not an error (grilling 2026-10-04).
  A matching key's list is used as given, even when empty: an optional choice then declines, a mandatory one fills to its minimum as usual, and an action branch with no matching preference is not offered.
  An entry's explicitly matching override answers its query ahead of any baseline preference, and otherwise each handler — the baseline included — weighs a query by the branch it has currently reached.
  A query no key matches, such as a single combined question for every type, is answered by the branch's own preferences.
  Presentation independence still holds: a test using per-question preferences passes for an engine that asks one annotated question per type, one that asks unannotated questions it can tell apart by what they offer, one that filters what it offers or offers everything and rejects a repeated pick, and one that asks a single combined question, wherever those presentations can be told apart (grilling 2026-10-04).
  The mapping is part of the branch: a rejection still moves to the next branch, and `act`, `act_illegal` and `Intent` take `per_query` for every branch as they take `choices`, after each branch's own.
  A key is a canonical object or a predicate; a raw string is refused.
- **Driving**: tests insert explicit pass entries for priority windows they skip, and a dry script passes through the Baseline Intent, which never takes an action at priority whatever its preferences.
  `advance_to_phase` consumes no entries; `run_scripts` stops once every script is consumed and leaves the stack in place, and `resolve_stack` then resolves with every player passing (grilling 2026-10-04).
  The priority round carries over between `run_scripts` calls — the next priority holder, the passes already made, and a resolution or step change both passes made due.
  The engine keeps that round with the game and starts a fresh one whenever an action is taken, an object resolves or the game moves to another step, and `resolve_stack` always starts one, even on an empty stack.
  The normal priority loop shares the same round, so handing play between it and `run_scripts` neither repeats nor skips a priority window.
  A cleanup step grants priority only when its actions performed state-based actions or put triggers on the stack (CR 514.3a): each such window starts a fresh round, both the turn loop and `run_scripts` give players priority in it — a script entry may act there — and another cleanup step follows once it ends; `advance_game_to_phase` and `resolve_stack` still finish cleanup with every player passing — leaving a window `run_scripts` paused in, they resolve what is pending and then perform the cleanup steps that follow until one grants no priority.
  An abandoned resolution stops every driver where it is — `priority_loop`, the turn's cleanup, `run_turn` and `run_game` as well as `run_scripts` and the forced helpers: none grants priority again, resolves what lies below, starts another cleanup, advances a step or fires a later event, and pending script entries stay pending.
  A later call resumes from there.
- **One step lifecycle**: the game owns where the current step is — its turn-based actions pending, its priority window open, or complete — and every driver, the turn loop, `run_scripts` and the test helpers alike, advances that one state, so a step's turn-based actions happen once whichever driver performs them, a step with no window (untap, a cleanup iteration that grants no priority) is never opened, and a completed step is never reopened.
  Live play shares one implementation of the turn-based actions — the starting player's first draw is skipped and a draw from an empty library is attempted; only the forced helpers' fast-forward skips combat declarations and draws just from a nonempty library, consuming no entries.
  `advance_to_phase` stays setup only: it marks the target step entered without its actions.
- **Choices outside the script**: choices raised while casting or resolving, including effect-granted casts such as Uldaros's or Bilbo's, go to choice Intents routed by source.
  A rejected choice is retried with the Intent's next branch as above; once its branches are exhausted the choice Intent fails, except that an `InvalidPlayerChoiceError` raised under a negative choice Intent counts as a pass once the engine has rolled back to the choice's rejection boundary, and the resolution continues from there (grilling 2026-10-04).
  A negative choice Intent's forbidden choice that takes effect fails the test with `PostconditionError` when its attempt completes, or at `end_intent` for a choice made outside any attempt; if the forbidden choice is never offered, nothing is checked.

### Rigor (three independent layers)

1. **Option-set invariants over the query transcript** — the harness logs every query raised (source, options, min/max, answer); tests assert pattern-based invariants over the log (e.g. every creature offered to sacrifice has controller = player0). Decomposition-robust; catches engines that offer illegal options even when the intent never picks one. HOB benchmarks only: from fra-hard-v2 onward, what was offered never fails a test and tests never assert over the transcript; only an illegal choice allowed to take effect does, judged by the Player View (grilling 2026-10-04, 2026-10-05).
2. **Postconditions** checked at `end_intent` (HOB); from fra-hard-v2 onward, expected Player Views checked at every action question (grilling 2026-10-05).
3. **Intent spreads as suite design**: each audited test asserts a single must-achieve intent; optionality is covered by separate tests per option (one test per color for "any color", plus a decline test where legal), including negative/impossible intents that must fail cleanly.
### Minimal engine enforcement

Two things legitimately remain engine-side:

1. Computing the legal option set (generalizes the existing `TargetRequirement.filter_fn`).
2. The spend-time predicate for restricted decisions (natural home: the existing `add_restricted` primitive).
The engine computes the options it offers and validates restricted decisions at use, but offering is not the guarantee: an engine may offer a choice it then rejects with `InvalidPlayerChoiceError`, and only a choice allowed to take effect is judged (grilling 2026-10-05).

### Worked example — "Add one mana of any color" (V1: sos_257)

For "T, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.":

- **Query**: source = the land's decisions; options = five MANA decisions (W, U, B, R, G), each carrying the `spend: instant_or_sorcery` Modifier; min = max = 1.
- **Intent**: preference = the general RED mana decision; postcondition = pool gains a red mana. The player picks the offered restricted-red because it satisfies RED (extra Modifiers never block matching). The Modifier is the spend restriction.
- **Suite spread**: one test per color (each must succeed — proves genuinely any-color), plus a spend-time check that the restricted mana cannot pay for a creature.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-017](../adr/ADR-017-priority-actions-are-player-queries.md) | Priority actions are Player Queries chosen through the players' answers |
| [ADR-018](../adr/ADR-018-audited-tests-play-as-two-players-at-a-table.md) | Audited Tests build a position, play it and judge it only as players at the table would |
