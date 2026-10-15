Status: RENAME RECORD

Date: 2026-10-14

# ADR-021: Evaluation-sense "regression" names are retired or renamed

## Renames

In an LLM benchmark, "regression" also reads as a model getting worse, so the evaluation sense of the word is gone.
Breaking behavior that worked is now a collateral mistake, measured by Collateral Tests, and the FDN and engine suites are no longer scored as dimensions of their own: their tests are Dependency Tests or Collateral Tests counted in the Net Card Score (ADR-020).

| Old | New |
| --- | --- |
| FDN Card Regression, Engine Regression (evaluation dimensions) | Retired. What they graded is the FDN suite and the engine suite |
| Combined Regression | Retired. The headline is the Net Card Score; the per-test record of what moved is the baseline comparison |
| Baseline Score, Known-Best Score | Retired. The Net Card Score's reference points 0 and 1 |
| regression Audited Tests, regression suites | FDN and engine Audited Tests, FDN and engine suites |
| a regression, Regressed (a test newly failing, and their count) | a collateral mistake, Broken |
| Run Record keys `card_correctness`, `fdn_regression`, `engine_regression` | `target`, `fdn`, `engine` |
| `combined_regression` and its `regressed` | `baseline_comparison` and its `broken` |
| unavailability reason `regression_not_evaluated` | `suite_not_evaluated` |
| Known Defect manifest `failing_tests` keys `fdn_regression`, `engine_regression` | `fdn`, `engine`, in manifest schema version 2 |

## Where the old names were replaced

- The glossary, specifications, `AGENTS.md`, `README.md`, `PROJECT_MAP.md` and operator documentation use the new names.
  No compatibility alias is part of the rename.
- The live ADR bodies apply name swaps only, with a dated Amendments reference to this record.
  ADR-016's reporting clause also changed in substance, which its own Amendments entry records.
- Source symbols, Run Record writers and readers, regrade outputs, `silverquillm top`, and the Known Defect manifests of the Known-Best Workspace, smoke and fra-hard-v2 use the new names.
  New Run Records carry a new schema version with the new keys.
- The hidden graded copies of the FDN Audited Tests in the Known-Best Workspace, smoke and fra-hard-v2 use the new names in their headers.
- The Results Repo's runbook and scripts use the new names and choose a record's keys by its schema version, through the Results Repo pull request that accompanies the bench's record change.

## Where the old names stay

- Run Records already published to the Results Repo are immutable and keep their keys; readers choose keys by record schema version.
- Re-grades already published under the Results Repo's `regrades/` keep the keys of the bench that graded them until they are graded again.
- Frozen benchmarks keep their bytes: hob-medium, fra-hard v1 and SOS, including their `data/fdn_regression_coverage.json` files and fra-hard v1's schema version 1 manifest.
- A locked Workspace keeps its agent-visible bytes, including the "Regression tests for FDN …" headers of fra-hard-v2's FDN Reference Tests.
- The ordinary software sense of "regression" is not part of the rename: regression guards in comments, and test files such as `test_known_best_gameplay_regressions.py`.
- History keeps its words: every Amendments log and Relevant PRs entry, the incident entries of KNOWN-ISSUES.md, `KEY_DECISIONS.md`, the legacy SOS results under `docker/`, the Results Repo's analyses and the published hob-medium article.
- The glossary lists the retired names as terms to avoid.

## Relevant PRs

- #242 — Renames the evaluation sense in the glossary, specifications, ADRs and operator documentation; the code, data and Results Repo follow with the Net Card Score's implementation.
