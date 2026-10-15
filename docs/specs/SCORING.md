Status: DRAFT

Last updated: 2026-10-15

# Scoring

How a Benchmark Run is scored: the Net Card Score headline, the test classes and Attributed Cards it counts, and the per-suite results kept for analysis.

## Context

The grader runs a benchmark's Audited Tests against the agent's harvested Workspace after the container exits.
Agent tests are harvested as artifacts but never scored, and comparisons between harnesses or guidance are made across separate runs, not as scoring categories.
The headline answers one question in units of working cards: how many more cards work after the agent's changes than before (grilling 2026-10-14).

## Design

### Graded suites

| Suite | Tests | Run against |
| --- | --- | --- |
| Target-card | `data/tests/audited/<set>/<card_id>/tests.py` | The agent's target `card_impl.py` files and harvested engine |
| FDN | FDN Audited Tests, `data/tests/audited/fdn/` | The pre-filled FDN implementations and the harvested engine |
| Engine | Audited Engine Tests, `data/tests/audited/engine/` | The harvested engine |

The engine suite grades `data/tests/audited/engine/` whenever that directory exists; hob-medium and SOS, frozen before the Audited Engine Tests existed, grade the host copy of their staged engine tests instead.
A benchmark target card from the FDN set (smoke's targets) is graded only in the target-card suite and left out of the FDN suite, so a stub target never counts as broken (grilling 2026-10-02).

From the HOB generation on, the Writable Engine is freely modifiable: there is no additive-only rule and no diff policing.
Audited Tests judge card behavior by simulating gameplay (Implementation-Agnostic Testing), so any engine change, renames and refactors included, is judged only by its consequences on the graded suites.
Engine churn (`engine_diff.patch`) is a diagnostic, never scored.

### Net Card Score

The headline of every Benchmark Run on smoke, fra-hard-v2 and later benchmarks is its Net Card Score (grilling 2026-10-14):

```
Net Card Score = (Cards Implemented + Cards Fixed − Cards Broken)
                 / (target cards + other cards hosting related Known Defects)
```

| Reference point | Score |
| --- | --- |
| Unmodified Workspace | 0 |
| Known-Best Workspace with the Test Oracle Impls | 1 |

There is no floor: a run that breaks more existing cards than it makes work scores below 0, and a run that wrecks the engine shows it (grilling 2026-10-14).

Every target card has at least one test counting toward it that the unmodified Workspace fails, so the unmodified Workspace scores 0 (grilling 2026-10-19).

A candidate's leaderboard score is the mean Net Card Score over the runs its analysis counts, from one Cohort graded on one grading-inputs digest, shown with the run count; there are no significance tests or confidence intervals.
Which runs count is the analysis's call, made from run attributes in the Results Repo, and a low score never leaves a run out.

### Test classes

Every Audited Test is exactly one of three classes (grilling 2026-10-14):

| Class | Which tests | Counts toward |
| --- | --- | --- |
| Implementation Test | A target-card test that depends on no Known Defect | Cards Implemented |
| Dependency Test | An FDN or engine Audited Test the unmodified Workspace fails because of a Known Defect, or a target-card test that fails once a Known Defect is put back into the Test Oracle Workspace | Cards Fixed, when its Known Defect is related |
| Collateral Test | An FDN or engine Audited Test the unmodified Workspace passes | Cards Broken |

- Only Known Defects are dependencies.
  An engine mechanic a target card needs but the baseline lacks is part of that card's implementation, because engine work is what the harder benchmarks measure.
- A Known Defect is related when at least one target-card test depends on it.
  The Dependency Tests of a Known Defect that is not related are left out of the score, and so is a Dependency Test that also depends on such a defect: fixing what the targets do not need earns nothing.
- A card-local workaround for a Known Defect earns nothing over fixing the engine: the target card's Dependency Tests do not count toward it, and no existing card is fixed.
- Collateral Tests are one group across the FDN and engine suites, so every engine breakage shows up as a broken existing card.

Which target-card tests depend on which Known Defect is found by putting each defect back into the Test Oracle Workspace and running the target-card suites, and is recorded in the benchmark's Known Defect manifest (see [KNOWN-BEST-ENGINE.md](KNOWN-BEST-ENGINE.md) → Known Defects).

### Attributed Cards

Every test the score counts has exactly one Attributed Card, so that one broken mechanic is roughly one broken card (grilling 2026-10-14):

| Test | Attributed Card |
| --- | --- |
| Target-card Implementation Test | The target card doing most of the work in it, even when the test sits in another card's suite |
| Dependency Test | The card hosting its Known Defect |
| FDN Collateral Test | Normally its own card |
| Engine Collateral Test | The base Workspace card hosting its mechanic |

- A mechanic is roughly one keyword or one rules subsection, such as trample, the legend rule or flashback; the grouping is best-effort.
- No card but a basic land hosts two mechanics.
  A mechanic's Collateral Tests and the Dependency Tests of its own Known Defect are one mechanic and share its card, which can then be fixed and broken at once.
  A defect hosted on a target is the exception: its mechanic's Collateral Tests stay together on one base Workspace card, so breaking the existing cards that use the mechanic still costs a card (grilling 2026-10-19).
  fra-hard-v2's {X}-cost Collateral Tests, across the FDN cards with {X} in their cost, count toward Wildwood Scourge.
- Each related Known Defect has its own host card; two related defects share one only when no other card fits, and that card is fixed only when both are.
- A test that exercises several mechanics counts toward the mechanic its assertion checks.
  A test involving several target cards counts toward the main card it tests, or is split into separate tests.
- Rules that no card's text names, such as turn structure, game start and end, playing lands and the mana pool, are hosted on the basic lands and never on other cards, so a failing basic land always means engine breakage.
  Several rules may share a land; engine breakage is rare, and a land broken twice still counts once (grilling 2026-10-19).
- Audited Engine Tests that check engine internals rather than a rules mechanic, such as the decision data layer, the card registry, the `card_impl.py` lint and the zone containers, are grouped by file onto basic lands or onto cards that host nothing else, so their failures count too.
- Host cards are base Workspace cards other than the benchmark's targets, but for a related Known Defect a target card cannot be tested without.
  Such a defect is hosted on that target card, because any agent that tests the card finds the defect: fixing it is part of implementing the card, which counts once (grilling 2026-10-19).
  fra-hard-v2's X-cost defect is hosted on Inside Information, whose effect does nothing while X is always 0.

The attribution is host-only benchmark data (see [KNOWN-BEST-ENGINE.md](KNOWN-BEST-ENGINE.md) → Attribution data).

### Counting

| Count | Cards |
| --- | --- |
| Cards Implemented | Target cards all of whose attributed Implementation Tests pass, and, for a target hosting a related Known Defect, all of whose Dependency Tests too |
| Cards Fixed | Other cards hosting a related Known Defect all of whose attributed Dependency Tests pass |
| Cards Broken | Cards with at least one attributed Collateral Test failing, or no longer executed |

Each count is all-or-nothing per card (grilling 2026-10-14).
A single test can swing a whole card, but counting cards keeps a card with thirty tests from outweighing one with ten, and separates candidates that per-test rates compress: fra-hard-v2's completed calibration runs passed 92–100% of their target-card tests but 2 to 11 of 11 cards.

### Deriving the score

The Net Card Score is derived when read, never stored (grilling 2026-10-14).
It is a pure function of a grade's per-test outcomes and baseline comparison, from a Run Record or a re-grade, together with the benchmark's Known Defect manifest and its attribution data, so correcting an attribution changes the score without regrading.
One package function derives it for `silverquillm top`, the regrade summaries, and `silverquillm net-card-score PATH...`, which prints it as one JSON line per Run Record or re-grade for the Results Repo's run table and analyses, which never compute it themselves.
The grading-inputs digest leaves the manifest and attribution data out, so an attribution correction needs no re-score; instead every derived score names the digest of the scoring data it used (`scoring_data_digest`, over `data/known_defects.json`, `data/attribution.json` and `data/target_attribution.json`), which an analysis states beside its cohort's grading digest.
Beside the score, a derived line carries each count's cards, the denominator and the host cards in it, the failing tests per Attributed Card by class, and the Dependency Tests left out.
A broken Audited Engine Test that no attribution key matches, such as one graded on older inputs whose file has since gone, still counts: as one broken card per test file, named `unattributed:<file>`.
A candidate whose engine breaks every test it is graded on is still scored: its expected tests that did not run, through an import error, a timeout or an early exit, fail (see Tests that did not run), so it scores at or below 0.

The score is unavailable, with a reason, when:

| Reason | When |
| --- | --- |
| the baseline comparison's reason | The baseline comparison is unavailable |
| `no_baseline_comparison` | The grade carries no baseline comparison |
| `suite_not_evaluated` | The bench could not grade the target-card suite |
| `no_scoring_data` | The benchmark has no attribution data or no schema version 2 Known Defect manifest (SOS, hob-medium, fra-hard v1) |
| `scoring_data_invalid: <why>` | The benchmark's scoring data breaks its schema |
| `unreadable_grade` | The record or re-grade cannot be read |

### Run Record results

A Run Record keeps every Audited Test's raw outcome, per suite, so that later analysis can reclassify without regrading (grilling 2026-10-14):

| Key | Content |
| --- | --- |
| `target` | Per target card: passed/total and each test node's outcome |
| `fdn` | Per FDN card: passed/total and each test node's outcome |
| `engine` | Passed/total and each test node's outcome |
| `run_metadata["baseline_comparison"]` | The FDN and engine Audited Tests whose outcome moved from the unmodified Workspace's |

Records written before the rename keep `card_correctness`, `fdn_regression`, `engine_regression` and `combined_regression`; Run Records are immutable, and readers choose the keys by record schema version.

The baseline comparison is carried by every Run Record and regrade output of a benchmark with a Known Defect manifest whose grading ran; a regrade output carries it top-level.

```json
{
  "available": true,
  "fixed": {
    "fdn": ["fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"],
    "engine": ["test_zone_change.py::test_counters_do_not_survive_leaving_the_battlefield"]
  },
  "broken": {"fdn": [], "engine": ["test_combat.py::test_first_strike_damage"]},
  "baseline": {
    "grading_inputs_digest": "sha256:…",
    "grading_code_digest": "sha256:…",
    "workspace_digest": "sha256:…",
    "grader_image_id": "sha256:…"
  }
}
```

- `fixed` and `broken` list, per suite and sorted, the Audited Tests whose outcome moved from the baseline reference grade's; a baseline-passing test the run no longer executes counts as broken, and a test the baseline never ran is ignored.
- `baseline` names the baseline reference grade's key (see [KNOWN-BEST-ENGINE.md](KNOWN-BEST-ENGINE.md) → Baseline reference grade).

When the comparison cannot be computed it is `{"available": false, "reason": "<reason>"}`, with the first reason that applies:

| Reason | When |
| --- | --- |
| `grading_inputs_changed_during_grading` | The grading inputs changed while the run or the baseline was graded |
| `suite_not_evaluated` | The FDN or engine suite has no tests to count: the bench could not grade it (`grading_support_missing`), or an older grade recorded no expected tests; a suite whose expected tests all did not run is evaluated, and its baseline-passing tests are broken |
| `baseline_workspace_incomplete` | The unmodified Workspace could not be copied in full |
| `baseline_grading_failed:<reason>` | Grading the unmodified Workspace failed |
| `baseline_incomplete` | The baseline reference grade is incomplete for any reason but the FDN coverage gap every run shares |

A regrade reuses an earlier output's comparison only when it is available or unavailable as `suite_not_evaluated`, which depends on the candidate's own grading; any other unavailable comparison is graded again on the next regrade, with no `--force` needed.

### Tests that did not run

Every suite the benchmark-parameterized grading path grades (each target card's, each FDN card's and the engine's, for Karn runs and their regrades) states how many test functions it expected and which of them did not run, with why (grilling 2026-10-13, #221).
The legacy SOS/FDN `evaluate` path, the historical `--image` lineage's compatibility runner, records none of these fields for its card results, which carry `expected_test_functions: null`, an empty `not_run` and no failure messages; its engine result comes from the same engine grading as Karn runs and carries all three.
The expected functions are collected statically from the authoritative test files, outside the process that runs the candidate's code, so a candidate cannot change what is expected.
Static collection follows pytest's `__test__`: a false value turns off a module, a class (and a subclass that does not set it back) or a function, and exactly `True` makes a function or class expected whatever its name; the value set last counts, so a later `X.__test__ = ...` or a redefinition overrides an earlier one. A function in a module, class or directory skipped at collection (including by a `conftest.py` skip) is `skipped`. A `Test*` class pytest skips for defining `__new__` is still expected, a known limitation no audited test meets.
A parametrized function counts once, and it ran if any of its cases ran.

| Reason | When |
| --- | --- |
| `import_error` | The function's test module or class failed to collect because an import failed |
| `collection_error` | The function's test module or class failed to collect for another reason |
| `collection_interrupted` | Another module's collection error stopped the suite before anything ran |
| `timeout` | The suite hit its time limit; a timed-out suite keeps no results |
| `skipped` | The function was skipped or marked xfail at run time, or its whole module or class was skipped during collection (a module-level `pytest.skip` or `pytest.importorskip`) |
| `pytest_exited` | pytest did not run its session to the end (a crash, `os._exit` with any exit status, an interruption such as `KeyboardInterrupt` or `pytest.exit`, or an internal error) before reporting the function |
| `not_reported` | pytest ran its session to the end without reporting the function |
| `grading_support_missing` | Authoritative grading support was absent, so the suite never ran |
| `candidate_code_missing` | The candidate's engine or cards directory was absent, so the suite never ran |

Every expected function that did not run counts as one failed test in its suite's score: the suite's `tests_total` is the nodes that ran plus the functions that did not, so a candidate cannot raise a pass rate by skipping a test or breaking its collection (grilling 2026-10-15).
In the Net Card Score it is a failing test of its class, so it keeps its card from being implemented or fixed, and a Collateral Test that did not run breaks its card.
Cards and the engine are counted the same way, from the reported nodes: a collection error is never a node of its own, whether a module or a class (`<file>::<Class>::<collection-error>`) failed to collect, and a node that failed in its setup, call or teardown is one failed node.
Only a result with no node reporting at all, such as an older one, falls back to pytest's summary counts.
A parametrized function that did not run counts once, since its case ids are not known statically.
`grading_support_missing` is the exception: a suite the bench could not grade stays unevaluated, because an absent evaluation is different from an evaluated implementation scoring zero.
A card whose tests all failed to run is therefore scored, at zero, rather than left uncovered; the baseline comparison already counts a baseline-passing node that did not run as broken.
Each card's own `tests_passed`, `tests_failed` and `tests_total` stay pytest's raw counts of the nodes that ran; the suite totals and pass rates apply this rule.
A grade whose suite reported errors other than test failures is incomplete; those errors are read from pytest's short test summary only, so a failing test's captured log line such as `ERROR    engine.game:…` is no grading error. That includes pytest not running its session to the end (a crash, `os._exit`, an interruption such as `KeyboardInterrupt` or `pytest.exit`, or an internal error), recorded as the error `pytest_exited: exit status N`; the nodes that ran before it keep their outcomes.
The grader's reporter records the end of each session with a value generated for that grading, so an exit status alone never makes a suite look finished: a candidate that calls `os._exit(0)`, `os._exit(1)` or `os._exit(5)`, or `pytest.exit` with any status, mid-suite still leaves it incomplete. The reporter withholds that record after an interruption or an internal error, seeing both before pytest's own terminal reporter (whose handler can fail again, for instance once candidate code has closed stdout), and writes it only for an orderly exit status; an exit status other than 0, 1 or 5 also makes a suite incomplete even with the record present. pytest's own stop after collection errors (status 2) keeps its collection-error diagnosis instead.
Each failing node also keeps a failure message: one printable line of at most 240 characters with object addresses masked, and at most 128 KiB per grade of message mappings as they encode in JSON, node ids and separators included, later ones dropped.
Not-run reasons and failure messages are diagnostics; only the not-run count enters a score.
Grades written before this rule count only the nodes that ran, so compare scores only across grades on the same grading code; a regrade applies the rule to an older record, and its `source.scores` keeps that record's own `complete` beside its counts.

### Diagnostics

The Net Card Score sits above a breakdown kept for diagnosis:

- each count's cards, and the failing tests per Attributed Card;
- each class's tests passed/total, and the Dependency Tests left out;
- each suite's tests passed/total, with failure messages;
- engine churn, the total lines changed in `engine_diff.patch`;
- efficiency: tokens, Run Cost and time per card, and score per dollar.

### Leaderboard format

```
| Rank | Candidate              | Runs | Net Card Score | Implemented | Fixed | Broken |
|------|------------------------|------|----------------|-------------|-------|--------|
| 1    | claude-opus-5-5/max    | 10   | 0.81           | 8.9         | 0.9   | 0.0    |
| 2    | gpt-6.1-sol/high       | 10   | 0.74           | 8.1         | 0.8   | 0.0    |
```

(Example format — not real results.)

### Earlier benchmarks

SOS, hob-medium and fra-hard v1 predate the Net Card Score and keep the results they reported (grilling 2026-10-14).
They report each suite's raw pass rate separately: target-card correctness (the test pass rate, and the card pass rate of cards passing every test), the FDN suite and the engine suite.
fra-hard v1 also reported the FDN and engine suites pooled, against the unmodified Workspace's grade.
hob-medium has no Known Defect manifest, and its graded suites carry no Dependency Tests for existing cards, so a Net Card Score cannot be derived for it.

SOS weights its card pass rate by Complexity Tier:

| Tier | Criteria | Weight |
| --- | --- | --- |
| Trivial | Vanilla creatures, basic lands, no rules text | 1x |
| Simple | Single keyword or one straightforward ability | 2x |
| Medium | Multiple abilities, triggers, or targeting | 3x |
| Complex | Multi-step abilities, replacement effects, modal spells | 4x |
| Expert | Planeswalkers, complex state machines, unusual mechanics | 5x |

Weighted Score = Σ(w_c × pass(c)) / Σ(w_c), where pass(c) = 1 if all of the card's Audited Tests pass.
Tiers are assigned by automated heuristics: rules text length, keyword count, ability count, target requirements, zone interactions and card type.

### Future Work

**Cross-eval**: Run each agent's tests against every other agent's implementations (N×N matrix). Requires a test harvester to collect and validate agent-written tests.

**Self-eval**: Run each agent's tests against its own implementations. Useful for measuring self-serving test bias.

**Test Quality scoring**: Audit survival rate, discrimination score, difficulty calibration, coverage. Requires cross-eval infrastructure.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-016](../adr/ADR-016-baseline-engines-may-carry-known-defects.md) | Baseline engines may carry Known Defects, graded against a separate Known-Best Engine |
| [ADR-020](../adr/ADR-020-net-card-score-is-the-headline.md) | The Net Card Score is the headline score |
| [ADR-021](../tombstone/ADR-021-rename-regression-to-collateral.md) | Rename record: evaluation-sense "regression" names retired or renamed |
