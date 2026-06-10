Status: SETTLED

Last updated: 2026-06-10

Scope: SOS (V1). The `DeterministicPlayer` scripting, two-channel host-side driver, and test-API conventions below are the frozen SOS paradigm. MSH audited tests use the Player Query / Player Decision intent protocol instead — see [MSH-DECISION-MODEL.md](https://app.notion.com/p/bea4c558a1d2493a82a7a841d85a8fb0).

# Audited Test Suite

**Audited tests** are the maintainer-curated grading suite used to score agent output; this spec defines their conventions. It also documents **Agent tests** — the `tests.py` agents write during a Tested Mode run — which are harvested as artifacts but never used for v1 scoring (test-quality scoring and cross-evaluation are v2 features; see Test Harvester). Two further test populations are out of scope here and defined in [CONTEXT.md](http://context.md/): **Engine tests** (the Engine Regression dimension) and **Platform tests** (the repo-tooling suite).

## Context

Unlike traditional benchmarks with pre-built test suites, SilverquiLLM-bench has agents generate tests as part of the benchmark. In v1, only audited tests are used for scoring. Agent-written tests are harvested for future promotion to the audited suite via a test harvester pipeline.

## Design

### Testing Philosophy: Implementation-Agnostic Testing

Audited tests follow **Implementation-Agnostic Testing** (see [CONTEXT.md](http://context.md/)): a test asserts *what a card does* — observable game-state outcomes — and must pass against *any* correct implementation, never coupling to one implementation's naming, internal structure, method names, or conventions. Operationally, audited tests are behavioral/outcome-based, canonical-engine-API-only, and `DeterministicPlayer`-scripted. This principle governs every Audited Test Category and Decision below.

### Evaluation Architecture

**Implementation Phase** (per agent):

The agent receives the full SOS card set in a Docker container with FDN cards as examples. Depending on the configured mode:

1. **Blind mode** — Agent implements all cards without writing or running tests.
2. **Tested mode** — Agent implements cards and writes tests, iterating at its own discretion.
Both modes produce `card_impl.py` per card. Tested mode also produces `tests.py` per card.

**Evaluation Phase** (after all agents finish):

1. **SOS Card Correctness** — Audited SOS tests against each agent's `card_impl.py` + agent's `engine_work/`
2. **FDN Card Regression** — Audited FDN tests against pre-filled FDN impls + agent's `engine_work/`
3. **Engine Regression** — Core engine tests against agent's `engine_work/`
Self-eval and cross-eval deferred to v2 (requires test harvester). Agent-written `tests.py` files are harvested as artifacts but not used for v1 scoring.

### Test Harvester (v2)

Agent-written `tests.py` files are harvested as artifacts from each run but not scored in v1. A future **test harvester** pipeline will:

1. **Collect** — Gather all agents' `tests.py` files across runs for each SOS card
2. **Validate** — Run each agent's tests against all agents' implementations to check correctness (tests that fail against all implementations are likely buggy)
3. **Deduplicate** — Identify redundant tests across agents (same behavior, different code)
4. **Score** — Measure test quality: discrimination (do tests differentiate good from bad impls?), difficulty calibration (passed by some but not all agents), coverage (behaviors tested)
5. **Promote** — Move validated, high-quality agent tests into `tests/audited/sos/` to strengthen the audited suite
This enables cross-eval (N×N matrix), self-eval, and test quality scoring as future evaluation dimensions. See [SCORING.md](http://scoring.md/) → Future Work.

### Agent test constraints

These constraints govern **Agent tests** (written by agents in Tested Mode, harvested as artifacts). **Audited test** conventions are defined above (Testing Philosophy) and in the Decisions and Audited Test Categories sections below.

- Tests **must** use `test_utils` helpers (`create_game`, `set_board_state`, `cast_spell`, etc.)
- Maximum **30 tests per card** (first 30 kept if exceeded) — prevents gaming via trivial test spam
- Tests import from the standardized `card_impl` path for cross-evaluation compatibility
- Each test tagged with a category: `basic`, `ability`, `edge`, `interaction`, `rules`
### Test Structure

```python
import pytest
from silverquillm.test_utils import (
    create_game, set_board_state, cast_spell,
    advance_to_phase, assert_zone_contains,
    assert_life_total, assert_battlefield_count,
)

class TestCardName:
    def test_basic_cast(self):
        game = create_game()
        # setup + assertions

    def test_core_ability(self):
        game = create_game()
        # setup + assertions
```

### Test Utilities API

```python
def create_game(player1_life=20, player2_life=20, seed=None) -> GameState: ...
def set_board_state(game, player, battlefield=[], hand=[], graveyard=[], mana_pool="", life=None) -> None: ...
def cast_spell(game, player, card_name, targets=None, choices=None) -> None: ...
def advance_to_phase(game, phase) -> None: ...
def declare_attackers(game, attackers) -> None: ...
def declare_blockers(game, blocks) -> None: ...
```

### Test Quality Guidelines

- Each test tests one thing
- Tests are independent (no shared state)
- Tests are deterministic (seeded randomness)
- Board state setup is minimal
- Assertions are specific (`assert_zone_contains(...)` not `assert len(...) == 1`)
### Test Count Expectations

| Card Complexity | Tests |
| --- | --- |
| Vanilla creatures / basic lands | 2-3 |
| Simple abilities | 5-8 |
| Complex cards | 10-20 |
| Planeswalkers | 15-25 |
| Full set (~250-300 cards) | ~2,000-4,000 total |

### Artifacts Per Card

Artifacts are scoped per run (one run = one agent/model). Layout matches [BENCHMARK-RUNNER.md](http://benchmark-runner.md/):

```javascript
results/{run_name}/cards/{card_id}/
├── card_impl.py              # Agent's implementation
├── tests.py                  # Agent's tests (tested mode only)
└── result.json               # Per-card evaluation results
```

### Replay Validation (Engine Correctness)

Engine correctness is validated by replaying recorded MTGA game data (sourced from 17lands) through the Python engine and verifying game-state checkpoints match recorded outcomes. This replaces the originally planned XMage differential testing — Replay Validation is more valuable because MTGA is WotC's own rules implementation, and cross-language Java↔Python comparison adds complexity without confidence.

The Replay Validation pipeline is live (built after FDN 001–291 completed; the first benchmark runs preceded it as Pipeline Validation Runs). For MSH, the same pipeline is adapted to drive the MSH engine through the intent-based DeterministicPlayer via a benchmark-parameterized engine target — see [MSH-DECISION-MODEL.md](https://app.notion.com/p/bea4c558a1d2493a82a7a841d85a8fb0) and [MSH-BENCHMARK.md](https://app.notion.com/p/b9345f23a8054d9898d3364fe2e00837).

## Decisions

- **Agents write their own tests**: Test quality is part of evaluation, not pre-built. [SETTLED]
- **test_utils required**: Guarantees consistent format for cross-evaluation. [SETTLED]
- **30 tests per card cap**: Prevents gaming via trivial test spam. [SETTLED]
- **Audited-only evaluation for v1**: Self-eval and cross-eval deferred to v2 (requires test harvester). v1 runs audited tests only across three dimensions. [UPDATED]
- **Audited tests are LLM-drafted, failure-reviewed**: Initial audited suites are generated by LLM agents, then failures during benchmark runs are reviewed and corrected by a human. Passing tests are accepted as-is. Test Audit Web Tool remains a future option for deeper curation. [SETTLED]
- **Audited test structure: per-card files**: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. Uniform structure across all sets for reuse. Evaluator swaps in any agent's implementation as `card_impl.py`. [SETTLED]
- **Unified test path**: All card tests (FDN and SOS) live under `tests/audited/{set_code}/{collector_number}/tests.py`. Former `tests/cards/` FDN tests merged into `tests/audited/fdn/`. One structure, one evaluator. [UPDATED]
- **FDN tests as regression suite**: FDN audited tests (`tests/audited/fdn/`) serve as the post-run regression check against the agent's Writable Engine. [SETTLED]
- **Behavioral testing**: Audited tests target observable game-state outcomes ("what the card does"), not card-text annotations ("what the card says"). Ability Words (Converge, Prepared, Opus, Paradigm, Miracle-the-ability-word, Landfall, etc.) are never asserted as keywords; only the behavior described by the text following the ability word is tested. Static structural assertions are limited to identity (name, type line, P/T, mana cost). [SETTLED — Grilling 2026-05-26]
- **Tests use only canonical-engine APIs**: Audited tests must be runnable against the agent-visible engine at `benchmarks/sos/workspace/engine/`. Tests never depend on extensions present only in the Test Oracle Workspace's engine. See ADR-010. [SETTLED — Grilling 2026-05-26]
- **Test Oracle Workspace validates audited tests**: Every audited test in `tests/audited/sos/` must pass against the matching Test Oracle Impl in `benchmarks/sos/data/test_oracle_workspace/cards/sos/{cn}/card_impl.py` before being committed. The validation harness `tests/test_audited_against_reference.py` enforces this in CI. [SETTLED — Grilling 2026-05-26]
- **Audited tests are integration-style**: The bulk of audited tests drive the engine end-to-end via `test_utils` helpers — `create_game` → `set_board_state` → `cast_spell` (or activate ability) → `resolve_top` → assert observable game state (zones, life, P/T, counters, triggers, stack contents). Direct calls into card internals (`on_resolve`, `register_triggers`, `get_targets`) are reserved for narrow unit-style probes where stack mechanics are demonstrably irrelevant; tests that bypass the harness must justify it in a comment. The integration path naturally supplies `chosen_targets`, `colors_spent`, paid costs, and priority state that direct `on_resolve` calls otherwise have to construct by hand — and exercises the same code paths an agent's implementation actually has to satisfy at runtime. [SETTLED — Grilling 2026-05-26] **[OVERRIDDEN — Grilling 2026-06-03: simulation-only via the AUDITED-TEST-API; direct ****`on_resolve`**** / internal probes no longer permitted. See Historical Context.]**
- **Choice scripting via canonical ****`DeterministicPlayer`**: Audited tests inject player choices through `DeterministicPlayer(name, script=[...])` — a flat FIFO of answers consumed in engine prompt order via the `choose_target`/`choose`/`choose_yes_no`/`choose_card` methods. No labeled choice dictionaries, no push-style `choices=` kwargs on `cast_spell`. Tests must order the script to match the engine's prompt sequence; mismatches surface as `ScriptExhaustedError` or wrong-type errors, both valid failure signals. [SETTLED — Grilling 2026-05-26] **[OVERRIDDEN — Grilling 2026-06-03: replaced by the host-side driver's two-channel model (directive queue + choice script). See Historical Context.]**
- **Observability is outcome-based**: Tests assert against post-cast/post-resolve game state (zones, life, mana-pool snapshot, stack contents, raised errors, P/T, counters, downstream effects of granted abilities). Never against internal flags (`_omniscience_active`, `_apply_miracle_to_hand`), prompt-log inspection, or method-name probes (`callable(getattr(card, "...", None))`). Mana-pool minimality — setting the player's pool to the smallest mana that legally pays for the spell — is the discriminator for alternative-cost mechanics: correct impls succeed, broken ones raise `CastingError`. [SETTLED — Grilling 2026-05-26]
- **`test_utils`**** lives in two parallel workspaces**: The canonical agent-visible `test_utils.py` at `benchmarks/sos/workspace/test_utils.py` is frozen per ADR-010 — it exposes the canonical engine's existing primitives. The oracle workspace's `test_utils.py` at `benchmarks/sos/data/test_oracle_workspace/test_utils.py` mirrors the canonical file (per ADR-010's 1:1 mirror rule) and is the **home for the host-side ergonomic helpers** added for audited tests: `set_mana_pool`, `set_hand`, `set_battlefield`, `set_library_top`, `set_graveyard`, `assert_on_stack`, `assert_in_zone`, `assert_casting_error`. There is no `silverquillm/test_utils.py`; the host-side layer lives entirely inside the oracle workspace's mirror. Audited tests develop against the oracle workspace's `test_utils.py` and are copied to the canonical audited path at `benchmarks/sos/data/tests/audited/` once green. [SETTLED — Grilling 2026-05-26, corrected 2026-05-27]
- **Phase 18 PR shape**: The Phase 18 audited-test rewrite ships as a single PR with one oracle-workspace setup commit followed by one commit per card pairing the Test Oracle Impl with its rewritten tests. Flagship card is **sos_57 Mana Sculpt** — the canonical alt-cost/restricted-mana case and the anti-pattern foil to FDN_57. Each card commit is independently bisect-friendly: running the harness against just that commit's oracle must produce green. CI gate goes green from commit 2 onward. sos_214 and any other Phase-18-surfaced cards are deferred to a Backlog follow-up sweep, not folded into this PR. [SETTLED — Grilling 2026-05-26, expanded 2026-05-27]
- **Per-card acceptance gate**: A Phase 18 audited-test rewrite is "done for a given card" only when all three hold: (1) all rewritten audited tests pass against the matching Test Oracle Impl via the validation harness `tests/test_audited_against_reference.py`; (2) the Test Oracle Impl matches verbatim `card_spec.json` semantics with **no engine-clamping shortcuts** — no FDN_57-style `cost_reduction()` overrides that the canonical engine then clamps away from the printed mechanic; if the canonical engine can't represent a printed mechanic faithfully, add an additive extension to `test_oracle_workspace/engine/` per ADR-010 rather than approximate; (3) a per-card peer-review checkpoint before the commit lands — catches silent xmage-template drift like the sos_257 "until end of turn" misread Sonnet 2026-05-27 and GPT-5.4 both pattern-matched. [SETTLED — Grilling 2026-05-27]
- **Benchmark tier locking (three tiers)**: A benchmark's lifecycle is an explicit tier in `benchmarks/sos/config.json`. **Beta** — everything editable. **Benchmarking** — `workspace/` locked; oracle impls/engine and audited tests still editable. **Released** — all three locked (workspace + oracle impls/engine + audited tests). Locking oracle impls at Released (beyond the original two-item note) prevents audited tests being silently invalidated post-release. Enforced by a CI check against the base branch's tier. SOS is currently in Benchmarking. See ADR-011. [SETTLED — Grilling 2026-05-28]
- **Tier transitions are forward-only**: Non-reversible except for grave, documented reasons. Benchmarking→Beta invalidates all existing benchmarks for that identity; Released→Benchmarking forces retraction of all published scores. Tier is flipped via human PR edit to `config.json`. The CI check enforces the **base branch's** tier and `config.json` is never a locked path, so a pure transition PR always passes and lowering-a-tier-plus-editing in one PR is structurally impossible — no carve-out or bypass label is needed. See ADR-011. [SETTLED — Grilling 2026-05-28]
- **Harvested results format**: The harvest script consolidates all `docker/<image>/validated_results/` into long-format **JSONL** — one row per `(image, run, card, test-node, pass/fail)`, fully denormalized, written in run-append order and grouped at query time. Each row stores the `tests.py` content hash to detect audited-test changes across runs. Coarser rollups are views over this base table. [SETTLED — Grilling 2026-05-28]
- **Investigation skill — combined, breadth-triaged, human-gated**: One combined skill does both failure-investigation and test-discovery (the manual v1 of the v2 Test Harvester). Fault attribution uses **cross-impl breadth only** (no oracle re-run): a test failing across many independent implementations is ranked as suspect. Breadth is a triage/prioritization heuristic, not an automated verdict — a human makes the final test-fault vs impl-fault call and the skill never auto-edits audited tests. Known tradeoff: breadth alone can't separate a convention-coupled test from a genuinely hard card; the human-review gate absorbs this. [SETTLED — Grilling 2026-05-28]
- **Discovery promotion bar — never verbatim**: Candidate tests mined from agent-written `tests.py` in Validated Results are never promoted as-is. They are rewritten to the audited standard (integration-style, behavioral/outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted), must pass the matching Test Oracle Impl gate (ADR-010) plus the canonical-API-only check, then clear human review. Promotion is legal only in Beta/Benchmarking — Released locks audited tests, so promotion stops at Release and scores don't drift afterward. [SETTLED — Grilling 2026-05-28]
- **Test-improvement tooling lives repo-side**: The harvest script is repo code at `scripts/harvest_validated_results.py`, output to `benchmarks/<bench>/analysis/harvested_results.jsonl`. The combined investigation/discovery skill is a Claude Code skill under `.claude/skills/` in the bench repo (e.g. `.claude/skills/test-investigation/SKILL.md`), version-controlled alongside the audited tests it edits. Not in `docker/<image>/skills/` (those mount into benchmark-subject agents — wrong audience). [SETTLED — Grilling 2026-05-28]
- **Workflow documented as a spec, not an ADR**: The harvest pipeline + investigation/discovery skill are captured in a new AUDITED-TEST-IMPROVEMENT-WORKFLOW spec plus these Decisions bullets; no dedicated ADR. ADR-011 stays scoped to locking and its CI enforcement. Rationale: ADRs record *why* we lock; specs record *how* the workflow operates. [SETTLED — Grilling 2026-05-28]
- **Implementation-Agnostic Testing (core philosophy term)**: The founding principle — a test asserts what a card *does* and must pass against *any* correct implementation, never coupling to naming, structure, or conventions — is named **Implementation-Agnostic Testing** (see [CONTEXT.md](http://context.md/) glossary). It is the formalized, strengthened restatement of the Phase 18 behavioral-testing direction and the principle every decision above serves. [SETTLED — Grilling 2026-05-28]
- **Workflow cadence — on-demand, gated before Release**: The harvest + investigation/discovery workflow runs on-demand (it is the manual v1), but a pass is **required before any Benchmarking→Released transition** — the last chance to fix tests before they are frozen. Not automated per-run in CI. See AUDITED-TEST-IMPROVEMENT-WORKFLOW. [SETTLED — Grilling 2026-05-28]
- **Oracle harness: stub detection via AST**: the validation harness `tests/test_audited_against_reference.py` distinguishes real Test Oracle Impls from empty stubs with `_is_stub_impl()`, which AST-parses `card_impl.py` and treats a class as real only when it defines a non-dunder method (e.g. `on_resolve`, `can_cast`, `get_targets`). Classes with only an `__init__` of attribute assignments stay stubs. AST parsing is robust where text/regex matching could be fooled. [Drained from KEY_DECISIONS 2026-05-30]
- **Oracle ****`test_utils`**** stack-resolution helpers**: in the oracle workspace's `test_utils.py`, `resolve_top()` resolves exactly one stack object (pop + resolve + state-based-action check) for fine-grained tests, while `_resolve_top_of_stack()` drains the entire stack in a loop; `cast_spell()` uses the latter to auto-drain triggers. [Drained from KEY_DECISIONS 2026-05-30]
- **Host-side driver, single-step resolution**: Audited tests advance via a host-side driver (`priority_loop`) that, each iteration, checks SBAs + places triggers, polls players APNAP for a directive, and — if no one acts — resolves **exactly one** stack object via `resolve_top` before re-polling. Not the engine's all-pass auto-drain. Keeps every resolution observable. [SETTLED — Grilling 2026-06-03]
- **Two-channel player scripting**: `DeterministicPlayer` exposes two separate ordered channels — a **directive queue** (`no_op` / `perform_action` / `perform_illegal_action`) for player-initiated priority actions, and a **choice script** (the canonical answer deque) for engine-prompted mid-cast / mid-resolution decisions. Dry on either channel = test fails (`ScriptExhaustedError`). [SETTLED — Grilling 2026-06-03]
- **Legality spans two exceptions**: `perform_action` / `perform_illegal_action` treat both `CastingError` (cast / play) and `AbilityError` (activate / mana-ability) as the rejection signal; the test never catches them directly. [SETTLED — Grilling 2026-06-03]
- **No ****`mana_spent`****, no ****`set_stack`****; counters limited**: Canonical has no `StackObject.mana_spent` and the API has no `set_stack`. Mana paid is measured via pool deltas (activate mana abilities, then `assert_mana_pool` before/after); stacked states are reached by casting. `assert_counters` covers only `+1/+1`, `-1/-1`, `loyalty` (canonical has no generic counter store), so a novel counter type cannot be asserted. [SETTLED — Grilling 2026-06-03]
- **API canonical-only; tests run against oracle**: The test API references only canonical-engine primitives, but audited tests run against the oracle (and each candidate) engine, which may drift. The API keeps functioning regardless; only the test *result* depends on the engine. Oracle-only mechanics (sos_57 mana_spent refund, sos_226 casualty, sos_201 miracle alt-cost, sos_245 affinity reduction, sos_1 / sos_120 GY→exile redirect) need no test-API support — each is exercised indirectly through canonical entrypoints + observable-state assertions. **Building this test API requires no change to any workspace engine.** [SETTLED — Grilling 2026-06-03]
- **Import boundary — tests import the engine they run on**: Audited tests import from `test_utils` **and** from the running engine (`engine.*` — the oracle when validated against the oracle, the candidate during evaluation), because card behavior emerges from engine churn and the test must drive the real engine. Portability comes from every candidate implementing the canonical public API, not from restricting imports. The canonical-only rule applies to the *test API* (`test_utils` + directive vocabulary) and the no-engine-modification guarantee — not to what a test imports. The simulation paradigm forbids **private-attribute poking** (`_script`, `_resolve_targets`); correct behavior comes from running the engine. [SETTLED — Grilling 2026-06-03]
- **Targets — directive-carried vs choice channel**: Player-initiated casts/activations carry their targets on the directive (`CastSpell(name, targets=[...])`, `ActivateAbility(source, ability, targets=[...])`); engine-initiated triggered abilities take no directive and have their targets/may-choices answered from the choice script. Replaces the old `_resolve_targets` poke. [SETTLED — Grilling 2026-06-03]
- **Non-standard casts compose test-API helpers**: Alternative-cost / alternative-zone player casts (sos_13 *Prepared*: back face from exile for {W}) use `CastSpell(from_zone=...)` / `CastSpellFree(from_zone=...)`, routing to thin test-API helpers that duplicate the canonical cast path for the alternate zone/cost (`cast_spell_from_exile`, a copy of `cast_spell` from exile). The test API composes/duplicates canonical behavior; it never modifies the engine. [SETTLED — Grilling 2026-06-03]
- **Deterministic RNG via seed-replacement**: Randomized effects (sos_97 Ral Zarek −7 coin flips) are made deterministic test-side — replace `game.rng` with a seeded `random.Random(seed)` and re-derive the expected value from an identically-seeded RNG (the pattern existing tests use). No engine change, no scripted-RNG channel. [SETTLED — Grilling 2026-06-03]
- **Self-draining resolutions are end-state-only**: A few oracle cards drain the stack inside their own `on_resolve` (sos_120 Improvisation Capstone), so a single `resolve_top` cascades internally and only the end state is observable between nested casts — acceptable under the canonical-only rule; assert final state, not the mid-cascade stack. [SETTLED — Grilling 2026-06-03]
- **Ability identity by printed-order index**: `ActivateAbility` names the ability by its index into the card's `get_activated_abilities()` / `get_loyalty_abilities()` (abilities assumed indexed in printed order, e.g. Ral Zarek +1/−1/−2/−7). No text matching, no engine-side ability ids, no engine change. [SETTLED — Grilling 2026-06-03]
- **`advance_to_phase`**** processes state, not priority**: fast-forward runs turn-based actions, triggers, and end-of-turn cleanup so state is correct on arrival (e.g. until-end-of-turn resets like sos_257 prowess) but opens no priority windows. Exception: a triggered ability that forces a choice (target/selection/yes-no) is still answered from the choice script; dry → fail. [SETTLED — Grilling 2026-06-03]
- **No SpecialAction directive (YAGNI)**: the directive vocabulary stays `CastSpell` / `CastSpellFree` / `ActivateAbility` / `PlayLand` — none of the 10 audited cards need a special action (face-up flip, suspend, etc.); add one narrowly only if a future card requires it. [SETTLED — Grilling 2026-06-03]
- **Color-count mechanics pinned by pool or mana-ability scripting**: for Converge / colors-spent (sos_4), make `len(colors_spent)` deterministic either by pre-setting the pool to exactly the needed colored mana (mana-minimality) or by scripting mana-ability activations to float only those colors — both valid — then `assert_colors_spent`. [SETTLED — Grilling 2026-06-03]
- **`mana=`**** on ****`CastSpell`**** is an optional test-side disambiguator**: default None lets pool contents / pre-cast mana-ability scripting determine payment; it is a directive field composed over canonical `cast_spell`, never an engine change. [SETTLED — Grilling 2026-06-03]
- **Arbitrary counter types deferred (YAGNI)**: `assert_counters` stays scoped to canonical `+1/+1`, `-1/-1`, `loyalty`; non-standard counters (charge, stun, oil, etc.) get no test-API support unless a future audited card forces it. Asserting a counter's *presence* is an internal-state probe anyway — assert its observable effect (P/T, mana produced, ability powered). [SETTLED — Grilling 2026-06-03]
- **Casualty (sos_226) tested as a granted keyword via the public choice API**: set up the granter + a sacrificeable creature + a subject instant/sorcery, `CastSpell` it, answer the "sacrifice which creature?" prompt from the choice script, and assert observable outcomes (sacrificed creature in graveyard + the spell resolving twice). The choice routes through the public `choose()` interface, so the oracle's `_handle_casualty` is updated to drop its private `_script` / `_pop()` poke (an oracle change; canonical untouched) — which also keeps the test portable across candidate engines. The oracle copies with the same targets, so retargeting is not asserted. [SETTLED — Grilling 2026-06-03]
- **Combat declarations are scripted on the choice channel, not as directives**: the canonical combat steps prompt via the engine's public `choose` (attackers = a list, blockers = a `\{blocker: attacker\}` dict, ordering via `assign_damage_order`), so attacking/blocking are answered from the `choices` queue (Channel 2), reached by `advance_to_phase` through the declare steps — no new directive and no engine change. [SETTLED — Grilling 2026-06-03]
- **Combat illegality is asserted by outcome, not ****`perform_illegal_action`**: the engine silently filters illegal attackers/blockers (non-flyer blocking a flyer, summoning-sick attacker) with no exception, so assert the observable result (e.g. the flyer's damage reached the player). `perform_illegal_action` stays for exception-signaled illegality — casts (`CastingError`), activations (`AbilityError`), incl. sos_97 once-per-turn loyalty. [SETTLED — Grilling 2026-06-03]
- **Multi-player turn control deferred (YAGNI)**: no `set_active_player` / start-of-turn helper; all 10 audited cards are testable within P0's turn (P0 attacks, P1 defends via choice-script blocks). `create_game` starts P0 active; reaching P1's turn or crossing a turn boundary is out of scope until a future card requires it. [SETTLED — Grilling 2026-06-03]
- **Simultaneous-trigger ordering deferred (YAGNI)**: no audited card puts multiple triggers on the stack at once needing a chosen APNAP/controller order (sos_257 prowess and sos_1's attack trigger fire singly; sos_120 self-drains inside `on_resolve`), so ordering machinery is not specified until a future card forces it. [SETTLED — Grilling 2026-06-03]
- **Two-channel player is a ****`test_utils`**** subclass, not an engine change**: the two-channel `DeterministicPlayer` subclasses the canonical single-channel player using only the canonical constructor signature; the directive queue is a subclass-only attribute polled by the Host-Side Driver, and the choice script maps onto the canonical answer deque. Reason: the evaluator pairs the oracle `test_utils.py` with each candidate engine — an engine-side `choices=` kwarg would `TypeError` against every candidate. [Drained from KEY_DECISIONS 2026-06-10]
- **Directive-carried targets ride a ****`_pending_targets`**** queue, not the choice deque**: cast targets are consumed by `choose_target` before falling back to the choice script; ability activations set the canonical `chosen_targets` convention on the source. Keeps the two channels independently ordered; leftover targets after a cast are a loud `TestSetupError`. Replaces the old `_script.appendleft` poke. [Drained from KEY_DECISIONS 2026-06-10]
- **Oracle cast pipeline fires ****`SpellCastTriggeredEvent`**: additive oracle-engine change per ADR-010 — all three cast paths fire the event after pushing the spell (after the casualty offer); spell copies fire nothing. Canonical untouched: candidates must implement whenever-you-cast semantics themselves. [Drained from KEY_DECISIONS 2026-06-10]
- **Creature SBAs skip declared non-creatures (oracle fix)**: the zero-toughness / lethal-damage SBAs skip objects whose `card_types` lacks CREATURE; objects with no `card_types` attribute stay duck-typed (preserves engine-test mocks). Found via the unanimated sos_257 land exposing `toughness == 0`. [Drained from KEY_DECISIONS 2026-06-10]
- **`_handle_casualty`**** prompts via public ****`choose()`**: the oracle's `DeterministicPlayer` special-case and `_pop()` poke are removed across all three cast paths; an unscripted prompt is a hard `ScriptExhaustedError`. The candidate power filter uses the counters-aware canonical `power` property, making the power-threshold behaviorally testable. [Drained from KEY_DECISIONS 2026-06-10]
- **sos_120 registers Paradigm hooks in ****`on_cast`**: sorceries never enter the battlefield, so replacement/trigger registration moved to `on_cast` (card-side change only); Paradigm copies are flagged and get no hooks; `set_board_state(exile=...)` also registers triggers for exile-placed cards. [Drained from KEY_DECISIONS 2026-06-10]
- **sos_226 ****`casualty_grant`**** is a read-only property**: defines a non-dunder member so the harness's AST stub-detector recognizes the impl as real — sos_226 was previously silently skipped by the validation harness; all 10 audited cards now actually run. [Drained from KEY_DECISIONS 2026-06-10]
- **`advance_to_phase`**** processes each step entered, within the current turn only**: the arrival step's turn-based action runs too (advancing to DECLARE_ATTACKERS performs the declaration from the choice script); targets at-or-before the current position raise `TestSetupError`; legacy declare helpers keep the raw `_jump_to_phase`. Fast-forwarding through combat with an eligible attacker requires a scripted attacker list. [Drained from KEY_DECISIONS 2026-06-10]
- **Conformance gate: curated AST ban-list + structural underscore rule**: flags banned simple-name calls and any leading-underscore attribute access (except `__init__` and attributes on `self`); imports are never flagged; fixture-card hook bodies are exempt (card-impl-kind code); collection-method names (`pop`, `add`, …) are flagged only when the receiver carries an engine marker. Scans the oracle audited tree plus the canonical copies so the two can't drift in conformance. Known limits: an engine object aliased to a neutral name slips the generic-name rule, and the repo has no CI workflow — the gate runs wherever `pytest tests/` runs. [Drained from KEY_DECISIONS 2026-06-10]
- **sos_57 fizzle test conforms to an oracle targeting quirk — not normative**: `get_targets()` returns the target pool and the cast pipeline prompts once per entry, so the test answers two target prompts, marked ORACLE-ENGINE QUIRK in-test. Do not treat the two-answer shape as the spec for future tests or candidate engines. [Drained from KEY_DECISIONS 2026-06-10]
- **Migration coverage consciously dropped/reshaped**: sos_57 second-main / refund-once / wizard-leaves variants (turn-crossing and mid-test removal deferred; a free-cast counter test recovers mana-spent coverage); sos_120 three-turn loop → single recurrence via exile setup; sos_4 mid-stack-removal fizzle → insufficient-mana `perform_illegal_action` negative; sos_97 −7 asserted via the recorded `skip_turns` attribute (no turn-skip machinery); keyword-presence asserts dropped per the behavioral doctrine. [Drained from KEY_DECISIONS 2026-06-10]
- **`priority_loop`**** never observes mid-stack state**: the driver terminates only when the stack is empty and queues are exhausted (dry queue + non-empty stack = `ScriptExhaustedError`), so stack assertions are exercised as ordered-emptiness / absence checks; doubled casualty resolution is asserted via the doubled observable result. [Drained from KEY_DECISIONS 2026-06-10]
## Audited Test Categories

Test patterns audited SOS tests may use, post Phase 18 audit. Tests target observable game-state outcomes; structural assertions are limited to identity sanity checks. The test shape is **simulation-only**, per [AUDITED-TEST-API.md](https://app.notion.com/p/8f73aba9c12e49449feef275f8470e96): `create_game` → `set_board_state` → script `DeterministicPlayer` directives → advance via `priority_loop` (or `advance_to_phase`) → assert observable state. Every category below assumes this shape; direct `on_resolve` / internal-probe shortcuts are no longer permitted (they were the old integration-style exception, now removed).

**Keep, slimmed**

- **`test_card_identity`**: name, `type_line` (literal printed string), `mana_cost`, P/T (creatures only). No keywords list. No separate CMC. Cheap typo guard that catches spec/impl name and cost drift.
**Keep, behavioral**

- **Printed-ability positive tests**: assert the card produces its stated effect under the natural cast/activate path. Core.
- **Ability-word printed behavior**: behaviors named by ability words (Converge color count, Paradigm self-exile-and-recur, Prepared alt-cost from exile, Opus-conditional bonus, Landfall, Heroic) are tested as ordinary printed abilities. The ability word label itself is not tested; the behavior its text produces is.
- **Granted-keyword behavior**: for granters (sos_201 grants Miracle, sos_226 grants Casualty, sos_245 grants Affinity), cast a subject card under the grant and assert the granted behavior fires. Never assert a presence flag on the subject.
- **Negative tests**: catches over-application — does NOT trigger when not attacking, does NOT grant to opponent's creatures, does NOT exile when sourced from a non-graveyard zone, etc.
- **`test_spell_to_graveyard_after_resolution`**: integration sanity check for instants/sorceries — confirms the spell actually resolved. Replace with `test_spell_to_exile_after_resolution` when the card's printed text specifies exile-instead (sos_1, sos_120). Skip entirely for permanents (sos_97 planeswalker, creatures) and lands (sos_257) — they don't take the stack-to-graveyard path.
**Replace with behavioral**

- **`test_has_<keyword>`**** for intrinsic keywords**: test the *effect* (Flying = blocker filter on non-Flying/non-Reach; Affinity = cost reduction; Deathtouch = damage-to-creature lethality), not `Keyword.X in card.keywords`.
**Cut**

- **`test_mana_cost_cmc`** separate from `test_mana_cost`: CMC is derived; redundant.
- **`test_has_<ability_word>`**: ability words have no rules meaning — only the printed text following the label produces behavior. Test the behavior, never the label.
- **`test_targets_only_<X>`** via inspecting `get_targets`: method-name coupling. Replace with attempt-illegal-target tests that assert the engine rejects/filters.
## Historical discussion captures (archived)

The raw discussion notes behind these decisions — **Proposed Audited Test Improvements (2026-05-28)** and **Proposed Philosophy Changes (2026-06-03)** — have been moved to [Historical Context](https://app.notion.com/p/3706a7adc8ed80baafd3e93e28bb6d33). All of their proposals remain in force and are captured as SETTLED entries in the Decisions log above.
