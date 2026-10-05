Status: DRAFT

Last updated: 2026-10-06

# Test Interface

The immutable interface through which Audited Tests build a game, play it and observe it, from smoke and fra-hard-v2 onward, and how Audited Tests are designed around it.

## Context

Audited Tests used to write engine state — the step, the active player, the mana pool, zones mid-game — and call the engine's own stepping functions, so every test was a driver of its own and depended on attributes a candidate's engine rewrite need not keep (#167).
The Test Interface replaces that with one way to build a game, one way to play it and one way to look at it.
The Player Query protocol it plays through is described in [Decision Model](DECISION-MODEL.md).

## Design

### Two players at a table

An Audited Test plays two novice players who have come to a board state: the engine tells them what they may do and what happens when they do it, and they notice only what is visible on the table (grilling 2026-10-05).
Tests therefore build a position, play it through the players' choices, and judge the result by what the players can see — never by an object's internal details.

The principle binds every Audited Test: target-card tests, FDN Card Regression and Audited Engine Tests (grilling 2026-10-05).
Reference Tests keep their current form, and the workspace documents define the Test Interface without describing how Audited Tests are written (grilling 2026-10-05).

### Ownership

The Test Interface is its own module, `test_interface`, with its documentation; both belong to the benchmark, the candidate does not change them, and grading pairs the benchmark's copy with the candidate's engine (grilling 2026-10-05).
Both are staged into the Workspace, so a candidate can run the real interface against its engine, beside a few tests that show how the interface is meant to be used and catch an engine change that would break it (grilling 2026-10-05).
The scripted player that answers queries is part of `test_interface`, not of the engine, so a candidate cannot change how graded tests answer; the engine keeps only the base `Player` protocol, and the rejection hook's `context` carries everything the player needs to tell which answer was refused (grilling 2026-10-05).
`test_utils` stays in the Workspace as the Reference Tests' helper module, keeping its signatures but built on `test_interface`'s scripted player, since the engine no longer answers through Intents; it is the candidate's like the rest of the Workspace, and grading never swaps it in (grilling 2026-10-05).
Audited Tests may also use host-side helpers built only on the Test Interface, such as a view diff, that never enter the Workspace (grilling 2026-10-05).
The interface is minimal yet complete — every helper a test needs, none duplicating another.

The Test Interface relies only on a small engine surface, which the workspace documents name and require to keep working beside the Player Query protocol (grilling 2026-10-05):

| Engine surface | Used for |
| --- | --- |
| Game construction | Building the starting position |
| The one stepping entry | `run` |
| `PlayerQuery`, `PlayerDecision`, the Player hooks, `InvalidPlayerChoiceError` | Answering queries and hearing rejections |
| `shuffle(cards)`, `choose_at_random(options, n)`, `flip_coin()` | Every random event, so the test decides its result |
| Zone containers, life totals, each object's `printed` class, the tapped flag, the current step, the active player, the player being asked, game over and winner | The Player View |
| Each object's and each offered option's physical card | Following a handle's card across zones and choosing it |

### Construction

`create_game(..., start=(step, active))` builds the starting position, with that step's priority window open, before play begins (grilling 2026-10-05).
It sets only:

- cards, by predefined class, in any zone, with each library an ordered list, and a permanent tapped where the test says so;
- life totals and mana in a pool, since the game starts inside the window;
- the step and the active player; the turn is 1 when seat 0 is active and 2 when seat 1 is, so the starting player's skipped first draw (CR 103.8a) still applies.

Permanents present at the start are not summoning sick, and a planeswalker starts with its printed loyalty.
Construction sets no counters, damage or effects, and never shuffles: anything else a test needs is reached through proper play (grilling 2026-10-05).
Every card it places has a handle; a test makes the ones it follows with `card(...)` before placing them.
Once play begins, state changes only through play: a permanent that must arrive mid-game is cast, or put there by an effect, never placed by a helper (grilling 2026-10-05).

### Playing

Tests take no actions themselves: they script what each player answers, let the game run, and the engine asks the players its questions — what to do with priority, what attacks or blocks, which target — with the options it offers (grilling 2026-10-05).
`run` plays the engine's one step lifecycle and answers every query from the players' scripts; there are no action wrappers, and the engine's own stepping — the priority loop, the turn loop and the step functions — is internal.

A test fails as soon as play diverges from its scripts, so `run` has no bound in game turns; what is bounded is the re-asking after a rejection, since each answer's owner must answer differently each time, from the branches the test wrote out (grilling 2026-10-05).
The test states the view it expects as play goes, and `run` compares the Player View with it as queries arrive; `run` stops (grilling 2026-10-05):

| When | Result |
| --- | --- |
| The view differs from the expected view | The test fails |
| A script runs out | The test passes if the final view is the expected one |
| More than 5 seconds pass between one query and the next | The test fails on the timeout; the whole test stays within 10 seconds ([Audited Test Conventions](AUDITED-TEST-CONVENTIONS.md) rule 4) |

Play also diverges, failing the test, when an `act` entry's action is not offered, is rejected with no branch left to answer from, or misses what it expects; when an `act_illegal` entry's action takes effect; when a query has nothing to answer it; when play reaches a player whose script is empty while another script still has entries; or when the game ends with entries left (grilling 2026-10-05).

Scripting a stretch of play, such as passing through a turn, uses helpers that build script entries and expected views from the rules alone; they need no engine, so they live with the Audited Tests on the host and never enter the Workspace (grilling 2026-10-05).

### Scripts

- **One script per player**: each player's script is an ordered list of entries, and it is the only source of answers — there are no choice Intents and no Baseline Intent, so choices that shape play, such as trigger order, replacement order or dividing combat damage, are scripted like any other (grilling 2026-10-05).
- **What an entry answers**: an entry answers the player's next action question — a Priority Query or a combat declaration — and every other question that player receives until their following action question: a target or face inside their own action, a trigger's target as it is put on the stack, a choice while an object resolves, or a discard the other player's spell asks of them (grilling 2026-10-05).
  When and how those questions come differs between engines, but which stretch of a player's play they fall in is fixed by the rules, so one mechanism answers them all.
- **Entry kinds**: `act` takes an action; `act_illegal` tries an action that must not take effect; `pass_priority` passes, or declares nothing at a declaration, and may carry choices for the questions that follow it, in branches like any entry's.
- **Preferences and branches**: an entry answers by preferences over Player Decisions, matched preference-major ([Decision Model](DECISION-MODEL.md) › Determinism, for its matching only, not its fill to the minimum), held as ordered branches, each an ordinary preference list that answers every question of the entry.
  A retry is never inferred: when the engine rejects an answer the entry owns, it answers the re-asked question from its next branch, so with branches [Gleam of Death, Glamdring] then [Glamdring] and Gleam of Death illegal, an engine that offers Gleam of Death at once and one that asks Glamdring and then the face both cast Glamdring on the retry (grilling 2026-10-04).
  A branch whose action is not offered is skipped.
  An `act` entry diverges when no branch's action is offered or no branch is left after a rejection; an `act_illegal` entry is satisfied when every branch is not offered or rejected, and diverges when any takes effect.
  A question the entry's current branch cannot answer — no preference, an empty list, no match, or too few matches — declines when it is optional, and diverges before any answer takes effect when it is mandatory, unless it offers only the one option it requires; a question that requires several of its options — an ordering question such as trigger order, whose answer is also an order — and a division of combat damage are always answered from the script, since filling them would choose the order or split for the test (grilling 2026-10-06).
  So an empty `per_query` list on a forced singleton completes it; on a mandatory choice of one of two options it diverges whichever order the options come in; a missing or partial order diverges; and a fully scripted order gives the same answer however the engine presents the options.
  Whether a branch may choose the same object again is the test's decision, made branch by branch: a branch may repeat an answer to see how the engine reacts — the test goes on if the view still matches, fails if it diverges, and falls back to its next branch if the engine rejects the repeat — and the fallback can then answer without repeating (grilling 2026-10-05).
  A branch marked `distinct=True` never chooses an object that an answer still in effect already chose for a question from the same source object; a rollback undoes those answers, and branches repeat freely by default (grilling 2026-10-05).
  Two questions that offer the same cards and say nothing of what they ask for can only be told apart this way: with one artifact creature C, `branch(C)` repeats C for its artifact and creature questions, and its fallback `branch(C, distinct=True)` chooses C once and declines the other, however the engine splits the question.
- **Per-question preferences**: a branch may map keys to the preferences that answer a question a key matches, `branch(A, B, per_query={CardType.ARTIFACT: [A], CardType.CREATURE: [B]})` (grilling 2026-10-04).
  A key is an object the question payload holds or a predicate over the query — its payload, offered options, source or bounds — so a test can tell questions apart best-effort when the engine attaches no payload; keys are tried in mapping order and the first match wins.
  A matching key's list is used as given, even when empty, under the same rule as the branch's own preferences — an optional choice declines, a mandatory one diverges unless it offers only the one option it requires — and an action branch with no matching preference is not offered; a question no key matches is answered by the branch's own preferences.
  A key is a canonical object or a predicate; a raw string is refused.
- **Declarations**: a branch answering a combat declaration names every creature it declares — a set, not ordered alternatives — and scoped answers say exactly what each attacks or blocks (grilling 2026-10-04).
  A scoped answer is never filled in or trimmed: when its choices are not all offered, or the declaration that would take effect gives a declared creature something else, that branch is withdrawn with nothing committed and the entry tries its next branch.
  Every declare-attackers step raises its declaration, even with nothing to declare; a declare-blockers step raises none when nothing attacks.
- **Expected views**: the constructed position is the first expected view, and each entry states the changes its answers cause — Bolt in the graveyard, player 1 at 17 life; a host-side helper applies them to the previous expected view (grilling 2026-10-05).
  A change says only what the view can show: a card, by handle or class, moves between zones; a token of a class appears on a player's side or leaves the game; an ability of a class goes on the stack or leaves it; a permanent becomes tapped or untapped; a player's life becomes a number; the game ends with a winner or in a draw.
  The helper works out the step, the active player and the player being asked from the rules and the script — priority order (CR 117), the turn structure, and each turn's draw from the known library — so a test states only changes to the board and life.
  There is one expected outcome per test, never alternatives: how an engine presents its questions may vary, and the test's branches absorb that, but every presentation must reach the same view (grilling 2026-10-05).
  At every action question and when `run` stops, the whole Player View must equal the expected view, so an unexpected side effect fails as surely as a missing one.
  Questions inside an action or a resolution are answered without a check, since what the view shows mid-action — whether a spell is already on the stack while its targets are chosen — depends on how an engine presents the action.
- **Chance**: every random event — a shuffle, a choice at random, a coin flip — goes through the engine surface's randomness hooks, and the Test Interface answers them from the test's chance script, like a stacked deck, so every engine reaches the same view (grilling 2026-10-05).
- **Plain-English script**: the host-side helper narrates each entry in plain English from the entry and its changes, so the narration cannot drift from what the test does, and a test may add a note saying what an entry checks (grilling 2026-10-05).
  A failure reports the narrated script up to where play diverged, the question then asked, and the expected view against the actual one.

### Player View

`view(game)` returns a frozen snapshot, and it is the only way an Audited Test reads the game (grilling 2026-10-05).
It shows:

- each player's library in order, hand, battlefield, graveyard and exile, and the stack;
- each player's life total;
- the current step, the active player, and the player being asked;
- whether the game is over, and who won.

Each object in it shows only what it is (its predefined card, face or token class), where it is (its zone; on the battlefield whose side it is on, elsewhere whose card it is), and whether it is tapped.
A snapshot `v` has `v.players[i]` with `.life`, `.library`, `.hand`, `.battlefield`, `.graveyard` and `.exile`, plus `v.stack`, `v.step`, `v.active`, `v.asked`, `v.game_over` and `v.winner`; each entry has `.card`, `.tapped`, `.owner`, and `.handle` for a constructed card, and `v.where(handle)` gives that card's zone (grilling 2026-10-05).
Power and toughness, counters, damage, keywords, summoning sickness, continuous effects and the mana pool are not in the view.
Neither are a stack object's targets or modes, nor what attacks or blocks what: those show in what happens, and leaving them out keeps engines free to model them — a creature that blocks several attackers — without a view to keep in step (grilling 2026-10-05).

The test plays both players, so nothing is hidden from it: it sees both hands and both libraries in order (grilling 2026-10-05).

### Judging by consequence

A property the view leaves out is tested by what it causes in play (grilling 2026-10-05):

| Property | Shown by |
| --- | --- |
| A +1/+1 counter on a 2/2 | It attacks unblocked and the opponent loses 3, or it blocks a 3/3 and stays on the battlefield |
| Flying | A non-flier's block, as `act_illegal`, does not take effect |
| Loyalty | Activating −3 on a 2-loyalty planeswalker is illegal: the engine rejects it with `InvalidPlayerChoiceError`, and the player goes on as if they never chose it, so the same planeswalker may still activate another loyalty ability that turn; a planeswalker reduced to 0 loyalty goes to its owner's graveyard |
| "Until end of turn" | The consequence is gone on the next turn |

Tests may need supporting cards for this, such as FDN creatures and basic lands.

Events are seen as changes in the view: a test compares the view before and after play — the opponent's hand shrank by one, a card went to exile — and never reads engine events, the trigger log or the query transcript (grilling 2026-10-05).
What a player was asked routes answers through the scripts, never assertions, since how a choice is presented is never judged.

A card is a physical object, so a test may keep a handle to a card it constructed and follow it across zones even though each zone change makes a new object (CR 400.7) — the Glamdring put in hand is now in exile (grilling 2026-10-05).
The engine names the physical card behind each object and each offered option — for an ability, its source permanent's card — so a handle in a script chooses that very card, never one that merely looks the same.
Tokens are not tracked that way: a token or other object made during play is found in the view by its class.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-017](../adr/ADR-017-priority-actions-are-player-queries.md) | Priority actions are Player Queries chosen through the players' answers |
| [ADR-018](../adr/ADR-018-audited-tests-play-as-two-players-at-a-table.md) | Audited Tests build a position, play it and judge it only as players at the table would |
