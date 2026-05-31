# TODO

Reference: [TEST-IMPROVEMENT-WORKFLOW.md](https://www.notion.so/b99a10aff98e4794856ce259e4916163) (the manual v1 Test Harvester), [ADR-010: Test Oracle Workspace Uses Independent Engine](https://www.notion.so/3517df19bf3c4b709ad6cbe40471c8b1) (Test Oracle Workspace gate), ADR-011 (Benchmark Tier locks), [CONTEXT.md](https://www.notion.so/3a3e1d4cf0384c3cb2735ae280b71918) glossary, and [TEST-SUITE.md](https://www.notion.so/a50ff4a1782e4badbc4419b6cbaface9) (audited-test standard). Goal: stand up the manual v1 test-improvement workflow — harvest Validated Results into a queryable dataset, run a combined investigation/discovery skill over it, and gate promotions into the audited suite. All test edits and promotions are legal only in Beta/Benchmarking (SOS is currently in Benchmarking). Decisions resolved 2026-05-30: harvest reads `docker/<image>/validated_results/<run>/` (vetted runs manually promoted out of `results/`); extend the evaluator to record per-test-node pass/fail; stamp `tests_hash` into `result.json` at eval time.

## Phase 19: Test-Improvement (Harvest) Workflow

Sequencing: items 1–2 (evaluator schema) gate the harvest, because the harvested rows depend on per-node outcomes and `tests_hash` in `result.json`; items 3–6 build the harvest script and breadth summary on top; items 7–8 add the investigation/discovery skill and its discovery miner (which consume the harvested dataset and breadth view); item 9 adds the promotion gate. Each item is a single self-contained commit that leaves the repo green. No standalone test-writing items — the executor's Tester writes tests per item.

---

- [x] **1. Stamp ****`tests_hash`**** into per-card SOS ****`result.json`**** at eval time**
  Detail: In `silverquillm/evaluator.py`, add a `tests_hash: str = ""` field to the `CardResult` dataclass. In `_eval_sos_cards`, before running pytest, compute the SHA-256 hex digest of the audited test file bytes (`test_file = audited_dir / cn / "tests.py"`) and set it on the `CardResult` before the `result.json` write — the existing `json.dumps(asdict(cr))` dump then carries it. This makes audited-test changes across runs detectable per the Harvested Results schema. Additive change only; leave all other `CardResult` fields and the counts/`errors` behavior untouched.

  Files: `silverquillm/evaluator.py` (`CardResult` dataclass + `_eval_sos_cards` hashing + result.json write).

  Testability: unit test that `result.json` contains a `tests_hash` equal to `hashlib.sha256(tests_py_bytes).hexdigest()`, that it is deterministic, and that editing `tests.py` changes the hash.

- [x] **2. Record per-test-node pass/fail outcomes in per-card SOS ****`result.json`**
  Detail: Today `_run_pytest_with_pythonpath` + `_parse_pytest_output` capture only summary counts and `FAILED`/`ERROR` lines, so passed node IDs are never recorded and the per-`(card, test_node, outcome)` rows the harvest needs cannot be built. Extend the SOS eval path to capture every node's outcome: add `--report-log=<tmp>/report.jsonl` to the pytest invocation in `_run_pytest_with_pythonpath` (pytest's built-in machine-readable JSONL), then parse the `TestReport` entries with `when == "call"` (plus `setup`/collection errors) into a list of `{"test_node": <nodeid>, "outcome": "pass"|"fail"}`. Normalize nodeids to the `tests.py::test_x` form. Add `test_nodes: list[dict] = field(default_factory=list)` to `CardResult`, populate it in `_eval_sos_cards`, and let the existing `asdict(cr)` write persist it. Keep `errors`/counts intact for back-compat. Map collection/setup errors to an `outcome: "fail"` row (use a synthetic node id if pytest provides none). Implements the resolved 2026-05-30 decision to extend the evaluator for per-node reporting.

  Files: `silverquillm/evaluator.py` (`_run_pytest_with_pythonpath` report-log capture + parser, `CardResult.test_nodes`, `_eval_sos_cards`).

  Testability: unit test on a synthetic card with one passing and one failing test asserts `result.json.test_nodes` lists both with correct outcomes and that `tests_passed`/`tests_failed`/`tests_total` still match the existing parser.

- [ ] **3. Scaffold ****`scripts/harvest_validated_results.py`**** (discovery + CLI + output path)**
  Detail: New utility script following the existing `scripts/` pattern (argparse CLI, `if __name__ == "__main__": main()`). Discover all Validated Results by globbing `docker/*/validated_results/*/` from the repo root; derive `image` from the `docker/<image>/` directory name and `run` from the `<run-name>` directory name (e.g. `sos-2026-05-16T19-49`). Read the source corpus from `docker/<image>/validated_results/<run>/` only — never the `results/` working dir (Validated Results are runs manually promoted out of `results/` after completing cleanly, per the 2026-05-30 decision). CLI flags: `--bench` (default `sos`), `--output` (default `benchmarks/<bench>/analysis/harvested_results.jsonl`), and optional `--image` / `--run` / `--card` filters. Create `benchmarks/<bench>/analysis/` if missing. This item establishes discovery + CLI wiring + output path only; row emission lands in item 4.

  Files: `scripts/harvest_validated_results.py` (new); creates `benchmarks/sos/analysis/`.

  Testability: unit test against a temp fixture tree of `docker/<img>/validated_results/<run>/` directories asserts discovery returns the expected `(image, run)` pairs and that `--image`/`--run`/`--card` filters narrow the set.

- [ ] **4. Emit long-format ****`harvested_results.jsonl`**** rows (one per ****`(image, run, card, test_node)`****)**
  Detail: For each discovered run, read each `cards/<card>/result.json` and emit one JSONL row per entry in `test_nodes` (from item 2). Row fields exactly per [TEST-IMPROVEMENT-WORKFLOW.md](http://test-improvement-workflow.md/) §1: `image`, `run`, `card` (the `cards/<card>/` dir name, e.g. `sos_57`), `test_node` (e.g. `tests.py::test_mana_sculpt_refund`), `outcome` (`pass`|`fail`), `tests_hash` (from result.json), `passed`/`failed`/`total` (per-card rollup counts copied onto every row), `complexity_tier` (optional — resolve from the card's `card_spec.json` `complexity_tier` key when available, else null), and `harvested_at` (ISO-8601 timestamp of this harvest run). Append rows in run order to the `--output` path. Keep the format fully denormalized — cross-impl breadth (item 6) is a query-time view over these rows.

  Files: `scripts/harvest_validated_results.py` (row builder + JSONL writer).

  Testability: integration test over a fixture run dir with two cards (mixed pass/fail) asserts the exact emitted rows: one row per node with correct `outcome`, propagated `tests_hash`, and rollup counts copied onto each row.

- [ ] **5. Back-compat harvest for legacy Validated Results lacking per-node data**
  Detail: Validated Results produced before items 1–2 have `result.json` with `errors` + counts but no `test_nodes` and no `tests_hash`. Handle them without crashing: when `test_nodes` is absent, derive `fail` rows by extracting pytest node IDs from the `errors` strings (lines like `FAILED tests.py::test_x - ...` / `ERROR ...`), and emit a single per-card rollup row (e.g. `test_node = "__rollup__"`) carrying the pass/fail/total counts so coverage stays queryable; passed-node identities cannot be reconstructed for legacy runs, so they are intentionally not enumerated. When `tests_hash` is absent, set it to null and continue. Log a per-run notice that the run contributed legacy (fail-node + rollup) rows only.

  Files: `scripts/harvest_validated_results.py` (legacy-detection branch in the row builder).

  Testability: unit test on a legacy-shaped `result.json` (errors + counts, no `test_nodes`/`tests_hash`) asserts fail rows are derived from `errors`, a `__rollup__` row is emitted, `tests_hash` is null, and no exception is raised on missing fields.

- [ ] **6. Add cross-impl breadth summary view (****`--summary`****)**
  Detail: Add a `--summary` mode (and a reusable function) that loads `harvested_results.jsonl`, groups by `(card, test_node, tests_hash)`, and computes cross-impl breadth = the count of distinct `image` values with `outcome == "fail"`. Emit a ranked report (highest breadth first — the tests the most independent implementations fail, i.e. the prime test-fault suspects) to stdout and a `benchmarks/<bench>/analysis/harvested_summary.json` sibling. Use stdlib/pandas grouping with no hard DuckDB dependency; note in a comment that loading into DuckDB or emitting a Parquet sibling is an optional future optimization. This breadth ranking is the triage signal the investigation skill (item 7) consumes — a prioritization heuristic, not a verdict.

  Files: `scripts/harvest_validated_results.py` (`--summary` flag + grouping/ranking + summary writer).

  Testability: unit test on a small fixture jsonl asserts breadth = distinct failing images per `(card, test_node, tests_hash)`, that the same node under a different `tests_hash` is counted separately, and that ranking is descending by breadth.

- [ ] **7. Author ****`.claude/skills/test-investigation/SKILL.md`**** (combined investigation + discovery skill)**
  Detail: Create the greenfield `.claude/skills/test-investigation/` directory and `SKILL.md` in Claude Code native skill format, version-controlled alongside the audited tests it edits — NOT under `docker/<image>/skills/` (those mount into benchmark-subject agents, the wrong audience). Frontmatter: `name: test-investigation`, a `description` of when to invoke, and the allowed tools/commands. Inputs: path to `benchmarks/<bench>/analysis/harvested_results.jsonl`; the target benchmark and its Benchmark Tier read from `benchmarks/<bench>/config.json` `tier` (must be Beta or Benchmarking — refuse if Released); optional card / test-node filters. Document the two modes of the one skill: (a) Investigation — for a failing `(card, test_node)`, rank by cross-impl breadth (via item 6) and present a test-fault vs impl-fault hypothesis for a human to decide, never auto-editing audited tests; (b) Discovery — surface promotion candidates from agent-written tests (item 8). Hard rules: breadth-only triage with no oracle re-run for attribution; the human makes the final fault call; canonical-engine-API-only when drafting; obey ADR-011 tier locks; promotion candidates must pass the matching Test Oracle Impl gate (ADR-010) before human review. Outputs are a human-reviewable report only — no committed test edits. Use [CONTEXT.md](http://context.md/) vocabulary (Harvested Results, Validated Results, Implementation-Agnostic Testing, Benchmark Tier, Test Oracle Impl) and reference [TEST-SUITE.md](http://test-suite.md/) for the audited standard.

  Files: `.claude/skills/test-investigation/SKILL.md` (new; also creates `.claude/skills/`).

  Testability: no runtime logic to unit-test; verify the [SKILL.md](http://skill.md/) has valid frontmatter (`name`/`description`/tools), points to the correct dataset path, states the Released-tier refusal rule, and documents both modes. A lightweight markdown/frontmatter structural check is sufficient.

- [ ] **8. Add the discovery-candidate miner used by the skill**
  Detail: Implement a helper — `scripts/mine_promotion_candidates.py` (or a `--discover` mode on the harvest script) — that scans the agent-written `tests.py` stored in each Validated Results `cards/<card>/` subtree and surfaces behaviors not represented in the canonical audited suite at `benchmarks/<bench>/data/tests/audited/<set>/<card>/tests.py`. Use a transparent heuristic (test function names, docstrings, asserted public engine APIs) to flag candidate behaviors; output a human-reviewable list of promotion candidates (card, source image/run, candidate behavior summary, source test snippet). This is Discovery-mode input for the skill (item 7) — it never promotes anything automatically. Respect `--bench`/`--card` filters for consistency with the harvest script.

  Files: `scripts/mine_promotion_candidates.py` (new) or a `--discover` mode in `scripts/harvest_validated_results.py`.

  Testability: unit test on fixtures where an agent `tests.py` exercises a behavior absent from the audited file asserts it is surfaced as a candidate, and that behaviors already covered by the audited file are not.

- [ ] **9. Implement the discovery→promotion bar gate**
  Detail: Implement `scripts/check_promotion_candidate.py` enforcing the promotion bar from [TEST-IMPROVEMENT-WORKFLOW.md](http://test-improvement-workflow.md/) §3 on a single rewritten candidate test before a human merges it: (1) run the candidate against the matching Test Oracle Impl via the Phase 18 validation harness in the Test Oracle Workspace (`benchmarks/sos/data/test_oracle_workspace/` + `tests/test_audited_against_reference.py`) — the ADR-010 oracle gate; must pass. (2) Run the canonical-engine-API-only check (reject if the test depends on engine primitives present only in the Test Oracle Workspace engine and absent from canonical `benchmarks/sos/workspace/engine/`). (3) Read `benchmarks/<bench>/config.json` `tier` and refuse promotion unless it is `beta` or `benchmarking` (Released locks audited tests, per ADR-011). Exit non-zero with a clear reason on any failure; this is an operational gate a human runs, never an auto-commit. Note: this gates one candidate — repo-wide Benchmark Tier lock enforcement (the ADR-011 CI check on the base branch) is a separate concern; flag it to the maintainer if that CI check does not yet exist rather than building it here.

  Files: `scripts/check_promotion_candidate.py` (new).

  Testability: unit tests — a candidate that passes the oracle gate and canonical-API check on a Benchmarking config is allowed; a candidate failing the oracle gate is rejected; any candidate is refused when `tier == released`.
