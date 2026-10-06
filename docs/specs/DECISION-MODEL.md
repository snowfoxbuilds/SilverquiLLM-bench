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
| source | tuple of Player Decisions | what raised it — routing matches on source refs (grilling 2026-10-05) |
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

Validation is engine-side: the query layer validates every query as it is raised — an option with an unknown kind or malformed attrs, or empty options where a choice is required, is an explicit, attributable engine failure (the `ProtocolError` family) — distinct from "no offered option satisfies the intent" (the `IntentError` family, attributable to the test). These two signal families replace `ScriptExhaustedError`.

Fault attribution requires propagation: card implementations must never catch exceptions raised by the query helpers (`choose_*` / `query_*`) — an `except Exception` wrapper silently converts a protocol or intent fault into a wrong game action (an unanswerable query becoming a default choice). Guards are legitimate only around APIs that signal failure by return value (e.g. `mana_pool.pay()` returns `False`, never raises).

### Concrete protocol surface (locked 2026-06-10)

Locked alongside the Task #1 implementation prompt; recorded here so the spec, not the prompt, is canonical.

**Module layout** — `engine/decisions.py` (kinds, decisions, refs, `satisfies()`, the Game Symbols vocabulary, exceptions), `engine/queries.py` (`PlayerQuery`, `Answer`, boundary validation), `engine/refs_registry.py` (Game Refs registry), `engine/player.py` (the `Player` ABC with the single entry point `answer(query) -> Answer`), `engine/intent_player.py` (`Intent`, `DeterministicPlayer`, query transcript) in the HOB engines; from smoke and fra-hard-v2 onward the players that answer tests belong to the tests instead — the [Test Interface](TEST-INTERFACE.md)'s `ScriptedPlayer`, and `test_utils.py`'s `DeterministicPlayer` for Reference Tests.

**Exception hierarchy** — engine-fault vs test-fault split:

```python
class ProtocolError(Exception): ...            # engine-side protocol failure
class UnknownKindError(ProtocolError): ...
class MalformedAttrsError(ProtocolError): ...
class InvalidOptionsError(ProtocolError): ...  # empty options with min > 0, malformed option

class IntentError(Exception): ...              # test-authoring failure
class AmbiguousIntentError(IntentError): ...
class UnmatchedQueryError(IntentError): ...
class InvalidAnswerError(IntentError): ...     # answer violates min/max or options membership

class InvalidPlayerChoiceError(Exception): ... # fra-hard-v2 onward: the engine rejects a chosen option as illegal under the rules
class PostconditionError(IntentError): ...
```

**Answer / decline** — `Answer(selected: tuple[PlayerDecision, ...])`: each element equals one of `query.options`, no duplicates, `min <= len(selected) <= max`, validated by the engine before applying. Decline is `Answer(selected=())`, legal iff `min == 0`; there is no separate Decline type.

**Ordering queries** — `min == max == len(options)`; the order of `Answer.selected` is the order chosen (trigger ordering).

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
  A declaration's one source is the declaring player's PLAYER decision with a `("window", "declare_attackers")` or `("window", "declare_blockers")` entry, matched by `declaration_pattern(window, seat)`.
  Like a Priority Query, a declaration is an action question, answered by the declaring player's script entry ([Test Interface](TEST-INTERFACE.md) › Scripts).
  What each attacker attacks and what each blocker blocks are follow-up queries sourced by that creature's OBJECT decision; the Known-Best Engine asks what an attacker attacks even when the defending player is the only choice, but an engine may skip a question with only one possible answer, so scoped answers are judged against the declaration that would take effect — what each declared creature attacks or blocks — never by which questions were asked.
  A forced choice — a query with only one possible answer, its single option or none — needs no decision: a player with no preference for it answers it anyway, and that answer owns a rejection only when no answer of the attempt made a decision.
- **Combat damage division**: an attacker blocked by two or more creatures has its controller divide its combat damage among them (CR 510.1c), replacing the damage assignment order (grilling 2026-10-05).
  The Known-Best Engine asks one NUMBER query per blocker, sourced by the attacker with that blocker's OBJECT decision as its question payload: how much of the damage still undivided that blocker is assigned.
  Without trample the last blocker is assigned the rest unasked; with trample every blocker is asked and the rest goes to the player or planeswalker attacked, and a division leaving damage over while a blocker is assigned less than lethal damage is rejected and asked again (CR 702.19c).
- **Trigger order**: a player whose triggered abilities trigger together puts them on the stack in the order they choose (CR 603.3b), through an ordering query per player in APNAP order whenever they control two or more of them (grilling 2026-10-05).
  Each option is an ABILITY decision carrying the triggered ability's `printed` class, its source's instance and its place among that source's abilities in the batch, and the first chosen is put on the stack first.
  Abilities wait from the moment they trigger, with that event's facts fixed then, until the game next settles before a player would receive priority (CR 117.5): every ability triggered since — by an action, a resolution, turn-based actions or state-based actions — is put on the stack then, the active player ordering and placing all of theirs, targets included, before the next player is asked.
  An ability keeps the source it triggered from: a source that leaves and returns before its abilities are placed is a new object, and the ability's source is the old one (CR 400.7).
  A state-based action that makes a player lose ends the game at once, so nothing waiting is put on the stack and no later step's damage is dealt (CR 104.2a).
  One player's placement is an attempt of its own, so a rejected target rolls back only that placement and is asked again.
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
  Every query's source ref carries `("printed", <class>)`, so an Intent routes by class; `test_utils` helpers take a predefined class (the first matching object) or the object itself and refuse a string.
  A synthetic test object stands for itself, and a test that must route or choose it by class gives it a test-local class.
  `scripts/printed_identity_codemod.py` converts name-based tests and, run with `--check`, enforces the rule over the Known-Best tests. It rewrites only string literals at sites whose card identity is certain — an argument to a helper the file imports and never rebinds, a `Decision` name or mode, a name pair in a `GameRef` card field, where `Decision` and `GameRef` are the engine's own classes, each imported once by name, unaliased, from `engine.decisions` or a module re-exporting that very class (such as `test_interface`), and never rebound — mapped through the card registry, and never infers values or bindings.
  Every other name-carrying site is reported instead of guessed — a name that is not a literal, a literal naming no predefined class, a name some object in the file is built with (or, when the file would otherwise convert, any object built with a computed name), a call through a rebound helper, a `Decision` or `GameRef` call whose binding the file does not establish as above (a second binding, a parameter, an alias, an import from another module, a qualified call), a card-naming pair outside a card field, a wildcard import in a file it would otherwise convert, a rewrite that would not compile — and a file with a report is left unchanged for a hand edit, so `--check` keeps failing until each is resolved.
  A name is rebound by anything in the file that binds it, in any scope: every identifier a syntax node carries counts as a binding except the few that only name something (an attribute, a keyword argument, a module), so a binding construct the codemod does not know makes a file manual rather than letting a rewrite through.

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
  Only that answer's player hears the error, through `Player.on_attempt_rejected(context, answer, error)`, after the rollback; it returns nothing, or raises to stop play, and the default raises.
  The engine then asks the same query again, as CR 733.2 leaves the player free to redo the action legally, take another or pass: a rejection never passes, ends or skips anything on the player's behalf, and the owner answers the re-asked query differently — its next branch, the next script entry, or declining — or raises (grilling 2026-10-05).
  The `context` names the attempt, the action it belongs to and that action's player, so no player is asked beforehand whether it would retry (grilling 2026-10-05).
  A rejection its owner raises, or one no answer owns, is final: the attempt has already rolled back to its own boundary, so the error passes every enclosing attempt without another rollback or notification, keeping what those attempts completed before it, and reaches the caller unchanged.
  Every Player hears rejections this way, whatever its preferences; state it keeps for its decisions is listed in its `rollback_exempt`, since a retry rolls the game back again — to the same boundary, after every hook has returned, for a priority action as for a resolution or explicit attempt.
  When the rejected choice inside a priority action is not the action itself, but another player's choice, that player's retry re-asks the Priority Query and the acting player chooses the same action again.
  Each action ends with exactly one `Player.on_action_ended(context)` to its acting player, and that is where the player lets go of the entry it acted on; these two hooks and `confirm_declaration` are the Player's whole rejection protocol (grilling 2026-10-05).
  Decision-side state — a player's script, transcript, script position and attempt bookkeeping — is not game state, and the rollback leaves it alone.
- **Retrying a rejected choice**: a retry is never inferred; the answer's owner answers the re-asked query from its next branch, as the [Test Interface](TEST-INTERFACE.md) describes for scripts (grilling 2026-10-04).
- **Resolution-time choices**: a choice raised while an object resolves, or while casting outside a Priority Query action, rolls back to its own rejection boundary — just before that cast or choice asked its first query — and is re-asked, answered from the owner's next branch.
  It never re-asks the Priority Query before it, which would replay the passes and resolve the object again (grilling 2026-10-04).
  What a resolution or explicit attempt runs outside the game — its callable and the popped StackObject, such as a spell copy that occupies no zone — is rolled back with the game.
  A resolution is one attempt whose boundary is its first query: a rejection runs the effect again from the state before it, re-asking the same query, and nothing is ever abandoned (grilling 2026-10-05).
  Card code that makes several casts or choices while resolving, such as Uldaros's copies, runs each as its own attempt (`attempts.attempt`), so a rejected later one keeps the earlier ones and is asked again — where it is optional, such as a cast the card allows, the player may then decline it and the resolution goes on without it.
  The normal priority loop and the test helpers resolve through the same engine attempt.
- **Testing choices whose presentation varies**: tests never dictate how an engine presents a choice; they are built to draw out the intended choice and to fail when an illegal one takes effect.
  Uldaros's targets are up to one card of each card type, judged by the graveyard characteristics of each card: the chosen cards must be distinct cards that can be assigned to distinct card types they have, though their type sets may overlap.
  Glamdring in the graveyard is an artifact card, never a sorcery (CR 715.4), whatever object an engine presents for it, so with Divination, Glamdring and Leyline Axe in the graveyard an engine fails if it lets all three be exiled; Divination with either artifact is legal.
  Choosing which face to cast happens later and separately, when a copy is cast (CR 715.3a): with Divination and Glamdring exiled, casting only the copy as Gleam of Death (mana value 4) and declining Divination stays within the budget of 6.
  Presentation varies only how questions are asked and answered, never what happens: a test's branches and per-question preferences are written so that every presentation converges on the same outcome, and the test expects that one outcome, never alternatives (grilling 2026-10-05).
- **Uldaros acceptance cases**: two artifact creatures fill the artifact and creature slots; one card is never chosen twice, so a single multi-type card is exiled and copied once — the suite may first repeat a card to probe the engine, falling back to a `distinct` branch when the repeat is rejected, so it converges under every presentation (grilling 2026-10-05); two cards that are only sorceries are never both chosen; and a copy's face is chosen while it is cast, whether the engine offers the faces in one query or across two.

#### Turn structure

How Audited Tests script the players' answers is part of the [Test Interface](TEST-INTERFACE.md); the engine side follows.

- **Passing is an answer**: declining a Priority Query is the player's answer, a pass, and an attempt reports no separate outcome; the window reads the answer to move the round on, and `run_game` plays until the game ends, with a winner or a draw, with no turn limit (grilling 2026-10-05).
- **Priority round**: a step's open priority window holds the round — who holds priority and how many players have passed in succession — and only the rules change it (CR 117.3–117.4): the window opens with the active player holding priority, a player who acts receives priority again, a pass moves it on, a resolution returns it to the active player, and every player passing in succession resolves the top object or, on an empty stack, ends the step (grilling 2026-10-05).
  No driver starts or resets a round; a paused `run` leaves the window as it is and the next call carries on from it.
  A cleanup step opens a window only when its actions performed state-based actions or put triggers on the stack (CR 514.3a), and another cleanup step follows once it ends.
- **One step lifecycle**: the game owns where the current step is — its turn-based actions pending, its priority window open, or complete — and only the engine's one stepping entry advances it, whether `run` or the turn loop calls it, so a step's turn-based actions happen once, a step with no window (untap, a cleanup step that opens none) is never opened, and a completed step is never reopened (grilling 2026-10-05).
  Playing with every player passing is a priority policy over that lifecycle, not a separate path; no helper writes the lifecycle, and only construction chooses the step play starts in.

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
