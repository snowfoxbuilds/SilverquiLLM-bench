Status: SETTLED

Last updated: 2026-04-28

# Test Suite

Agents write their own tests. In v1, agent tests are harvested as artifacts; scoring uses audited tests only. Test quality scoring and cross-evaluation are v2 features (see Test Harvester).

## Context

Unlike traditional benchmarks with pre-built test suites, SilverquiLLM-bench has agents generate tests as part of the benchmark. In v1, only audited tests are used for scoring. Agent-written tests are harvested for future promotion to the audited suite via a test harvester pipeline.

## Design

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

### Test Constraints

- Tests **must** use `test_utils` helpers (`create_game`, `set_board_state`, `cast_spell`, etc.)
- Maximum **30 tests per card** (first 30 kept if exceeded)
- Tests import from standardized `card_impl` path for cross-evaluation compatibility
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

The Replay Validation pipeline is built after all FDN 001–291 cards are implemented. First benchmark runs proceed without it as Pipeline Validation Runs.

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
- **Audited tests are integration-style**: The bulk of audited tests drive the engine end-to-end via `test_utils` helpers — `create_game` → `set_board_state` → `cast_spell` (or activate ability) → `resolve_top` → assert observable game state (zones, life, P/T, counters, triggers, stack contents). Direct calls into card internals (`on_resolve`, `register_triggers`, `get_targets`) are reserved for narrow unit-style probes where stack mechanics are demonstrably irrelevant; tests that bypass the harness must justify it in a comment. The integration path naturally supplies `chosen_targets`, `colors_spent`, paid costs, and priority state that direct `on_resolve` calls otherwise have to construct by hand — and exercises the same code paths an agent's implementation actually has to satisfy at runtime. [SETTLED — Grilling 2026-05-26]
- **Choice scripting via canonical ****`DeterministicPlayer`**: Audited tests inject player choices through `DeterministicPlayer(name, script=[...])` — a flat FIFO of answers consumed in engine prompt order via the `choose_target`/`choose`/`choose_yes_no`/`choose_card` methods. No labeled choice dictionaries, no push-style `choices=` kwargs on `cast_spell`. Tests must order the script to match the engine's prompt sequence; mismatches surface as `ScriptExhaustedError` or wrong-type errors, both valid failure signals. [SETTLED — Grilling 2026-05-26]
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
- **Workflow documented as a spec, not an ADR**: The harvest pipeline + investigation/discovery skill are captured in a new TEST-IMPROVEMENT-WORKFLOW spec plus these Decisions bullets; no dedicated ADR. ADR-011 stays scoped to locking and its CI enforcement. Rationale: ADRs record *why* we lock; specs record *how* the workflow operates. [SETTLED — Grilling 2026-05-28]
- **Implementation-Agnostic Testing (core philosophy term)**: The founding principle — a test asserts what a card *does* and must pass against *any* correct implementation, never coupling to naming, structure, or conventions — is named **Implementation-Agnostic Testing** (see [CONTEXT.md](http://context.md/) glossary). It is the formalized, strengthened restatement of the Phase 18 behavioral-testing direction and the principle every decision above serves. [SETTLED — Grilling 2026-05-28]
- **Workflow cadence — on-demand, gated before Release**: The harvest + investigation/discovery workflow runs on-demand (it is the manual v1), but a pass is **required before any Benchmarking→Released transition** — the last chance to fix tests before they are frozen. Not automated per-run in CI. See TEST-IMPROVEMENT-WORKFLOW. [SETTLED — Grilling 2026-05-28]
- **Oracle harness: stub detection via AST**: the validation harness `tests/test_audited_against_reference.py` distinguishes real Test Oracle Impls from empty stubs with `_is_stub_impl()`, which AST-parses `card_impl.py` and treats a class as real only when it defines a non-dunder method (e.g. `on_resolve`, `can_cast`, `get_targets`). Classes with only an `__init__` of attribute assignments stay stubs. AST parsing is robust where text/regex matching could be fooled. [Drained from KEY_DECISIONS 2026-05-30]
- **Oracle ****`test_utils`**** stack-resolution helpers**: in the oracle workspace's `test_utils.py`, `resolve_top()` resolves exactly one stack object (pop + resolve + state-based-action check) for fine-grained tests, while `_resolve_top_of_stack()` drains the entire stack in a loop; `cast_spell()` uses the latter to auto-drain triggers. [Drained from KEY_DECISIONS 2026-05-30]
## Audited Test Categories

Test patterns audited SOS tests may use, post Phase 18 audit. Tests target observable game-state outcomes; structural assertions are limited to identity sanity checks. The default test shape is integration-style: `create_game` → `set_board_state` → `cast_spell` or activate → `resolve_top` → assert. Every "Keep behavioral" category below assumes this shape unless explicitly noted; `on_resolve`-direct probes are the exception, not the rule.

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
## Proposed Audited Test Improvements (Discussion 2026-05-28)

Status: DRAFT — raw conversation capture, to be cleaned up later.

Motivation: there have been a lot of issues with audited tests so far. This section records a set of proposed improvements.

### Core philosophy

- Audited tests should test **what a card does** (functionality) rather than **how it uses certain conventions** (naming).
- Audited tests should work on a variety of different correct implementations.
### Three-tiered benchmark locking

Goal: make benchmarks consistent. A benchmark's tier is recorded under its benchmark config (e.g. `benchmarks/sos/config.json`).

- **Beta** — everything can be modified.
- **Benchmarking** — workspace is LOCKED; oracle impls and audited tests can still be modified.
- **Released** — both workspace and audited tests are LOCKED.
The SOS benchmark today is in the **Benchmarking** state.

### How to improve audited tests

- A script to harvest full test results from all `validated_results` in the repository.
- A skill that lets an agent investigate test results to determine whether failures are due to the tests or the implementation.
- The same skill should also explore tests written in benchmarks to discover cases not covered by existing audited tests, and turn them into audited tests.
### Clarifications (2026-05-28)

- **`validated_results`**** location**: harvested from `docker/<image>/validated_results/`.
- **Lock enforcement**: benchmark-tier locking (Beta / Benchmarking / Released) is enforced via a **CI check**.
- **Skill shape**: failure-triage and test-discovery are **one combined skill**, not two.
- **Fault attribution**: when a test fails, the skill **flags it for human review** to decide test-fault vs impl-fault (it does not auto-attribute or auto-fix).
- **Relation to Test Harvester**: the discover-and-promote skill is the **manual v1 of the planned v2 Test Harvester**.
### Resolved (2026-05-28)

- **Philosophy is a formalization, made stronger**: same direction as the SETTLED Phase 18 behavioral-testing decisions, restated and strengthened — not a change in direction.
- **Released tier vs. Test Harvester**: by design, the Test Harvester is **not run after release**. Therefore audited tests stay locked after release and **benchmarking scores do not change** once a benchmark is Released. (Promotion via the harvester only happens before Released.)
