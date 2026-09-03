Status: SETTLED

Last updated: 2026-05-24

# Workspace Contract

The Workspace is the only evaluatable state an Agent Container can produce. The runner stages the Workspace, mounts it at `/workspace/`, snapshots it during execution, and materializes the official evaluation Workspace as `docker/<image-dir>/results/<run_name>/workspace_final/`.

## Context

The benchmark now treats agents as black-box containers working in a real codebase-shaped Workspace. To keep evaluation deterministic and audit-safe, the Workspace layout is a contract. Agents may edit implementation files and engine code, but they must preserve the expected directory structure.

## Design

### Source of truth

The workspace contents are defined by the directory at `benchmarks/sos/workspace/` in the bench repo. Staging is a wholesale `cp -r` of that directory into a per-run tmp path, plus per-run writes for `prompt.md` and `run_manifest.json`, followed by `git init`. There is no per-file staging logic; to change what agents see, edit `benchmarks/sos/workspace/` directly. Tests should also be runnable locally from that directory (`cd benchmarks/sos/workspace && pytest cards/fdn/ && pytest engine_tests/`) — that is how we keep the workspace honest in dev.

### Resume staging variant

`silverquillm resume <prior-run-id>` uses a staging variant that copies the prior run's `workspace_final/` wholesale into the per-run tmp directory, then overwrites only `prompt.md` and `run_manifest.json`. No `git init` — the prior `.git` history (host snapshots and any agent commits) is preserved as the new run's `.git`. The Workspace Contract itself (layout, card directory invariant, the SOS (V1) additive-only engine rule) is unchanged: the resumed agent inherits the prior run's compliance state. Resume staging is otherwise identical to fresh staging — mount the copy at `/workspace/`, same volumes, same `/output/` channel. See [BENCHMARK-RUNNER.md](BENCHMARK-RUNNER.md) → Resume for the runner-side CLI, refuse conditions, and Resume Preamble; see ADR-008 for design rationale.

### Workspace layout

```plain text
/workspace/
  AGENTS.md             # entry-point doc for the agent
  PROJECT_MAP.md        # map of files and their responsibilities
  prompt.md             # per-run User Prompt (written at stage time)
  run_manifest.json     # per-run manifest (written at stage time)
  rulebook.txt           # MTG rules reference
  pytest.ini            # test config (workspace-local)
  .gitignore
  .git/                 # initialized at stage time, single seed commit
  engine/               # canonical engine source (shared with bench tooling)
  skills/               # bench-authored agent skills (copilot SKILL.md format)
    grep-rulebook/
      SKILL.md          # how to grep RULEBOOK.txt efficiently
  conftest.py
  test_utils.py
  test_utils.md
  engine_tests/         # engine regression tests (per ADR-006)
  cards/
    fdn/
      fdn_{collector_number}/
        card_spec.json
        card_impl.py    # filled reference implementation
        tests.py        # FDN Reference Test (illustrative, passing)
    sos/
      sos_{collector_number}/
        card_spec.json
        card_impl.py    # SOS Card Stub: class CardName(CardImpl): pass
        tests.py        # optional, agent-written in Tested Mode
```

### Run Manifest

Immediately before container launch, the runner writes:

```json
{
  "timeout_seconds": 7200,
  "deadline_utc": "2026-05-13T22:22:00Z"
}
```

The Run Manifest is advisory runtime context only. It is not agent configuration. Mode, strategy, model selection, and prompt behavior remain baked into the Docker image.

### Card directory contract

Each card keeps its canonical implementation in:

```plain text
cards/{set}/{card_id}/card_impl.py
```

FDN card directories use the `fdn_` prefix: `cards/fdn/fdn_{collector_number}/card_impl.py`. SOS card directories use the `sos_` prefix: `cards/sos/sos_{collector_number}/card_impl.py`.

The canonical implementation class for a card must be importable from that file. The agent must not move or rename card directories.

Failure scope:

- A missing or moved `cards/sos/sos_{collector_number}/card_impl.py` is a card-level failure.
- Many moved cards fail individually.
- A missing or unreadable `cards/sos/` tree is a run-level structural failure.
- A missing or unusable `engine/` follows engine viability and snapshot fallback flow.
### FDN and SOS structure

FDN examples and SOS targets use the same directory contract.

- FDN `card_impl.py` files are filled reference implementations.
- SOS `card_impl.py` files start as templates for the agent to fill.
This keeps examples directly comparable to targets.

### Shared helpers

Shared helper files are allowed as long as each card class remains in the expected card file and folder.

Examples:

```plain text
cards/fdn/utils.py
cards/sos/utils.py
```

Avoid cross-card directory imports. Hidden dependency chains make examples harder for agents to learn from and harder for the runner to stage and evaluate.

### Writable Engine

Agents modify `/workspace/engine/` in place. There is no separate `engine_work/`.

The baseline engine remains on the host side, outside the container. After the run, the runner diffs the official evaluation Workspace's `engine/` against the host baseline engine to produce `engine_diff.patch`.

For the HOB-generation benchmarks the engine is **freely modifiable** and `engine_diff.patch` is a **diagnostic** artifact only — never scored, never policed. The SOS (V1) additive-only rule below does not apply to them; see [HOB-BENCHMARKS.md](HOB-BENCHMARKS.md) → Engine rules and [SCORING.md](SCORING.md) → Agent envelope.

### Agent prompt rule

The SOS (V1) prompt states three hard rules — card location, staged-test integrity, and additive-only engine modifications (the additive-only rule is SOS-scoped; the HOB-generation prompts drop it, per the SCOPED decision below):

```plain text
Each card's implementation class must remain in its assigned
cards/sos/sos_{collector_number}/card_impl.py file. Do not move or rename card directories.

Do not modify any files under workspace/engine_tests/ or any FDN
reference test files at workspace/cards/fdn/*/tests.py. These tests
are for your local verification and learning only; the runner uses its
own authoritative copies for grading. Modifying these tests will not
change your score — it will only mislead you about whether your
engine changes are correct or whether you understand the testing
pattern.

Engine modifications must be additive. You may add new methods, classes,
helpers, and files inside engine/. You may modify the bodies of existing
functions to implement card behavior. You MUST NOT rename, move, or delete
anything that already exists in engine/ — no renaming, no refactoring.
Restructuring the engine will break the grader's imports and zero your
score regardless of card-implementation quality.
```

The prompt does not need to mention shared helper files.

## Decisions

- **Workspace is a pre-built directory copied wholesale**: The workspace source lives at `benchmarks/sos/workspace/` in the bench repo. Staging is `cp -r` + per-run writes (`prompt.md`, `run_manifest.json`) + `git init`, not per-file assembly. This keeps the workspace inspectable, dev-testable (`cd benchmarks/sos/workspace && pytest`), and removes drift between staging code and spec.
- **Workspace is evaluatable state**: Evaluation reads from `docker/<image-dir>/results/<run_name>/workspace_final/`, not from `/output/`.
- **Run Manifest is advisory**: `/workspace/run_manifest.json` contains only `timeout_seconds` and `deadline_utc`; the runner remains the hard timeout authority.
- **No ****`engine_work/`**: Agents modify `/workspace/engine/` in place. The host baseline is used for diffs.
- **Card class location is hard contract**: Each card's canonical implementation class must be importable from `cards/{set}/{card_id}/card_impl.py`.
- **FDN and SOS share structure**: FDN examples and SOS targets use the same card directory shape.
- **Card restructuring is card-level by default**: Individual misplaced card files fail those cards; broad Workspace destruction can become run-level failure.
- **Engine tests are staged into the workspace**: Per ADR-006, the workspace includes `workspace/engine_tests/` so agents have a local regression-check loop for engine modifications. Grading uses host-repo copies; agents are prompt-instructed not to modify staged tests.
- **FDN reference tests are colocated with cards**: Illustrative FDN tests live at `workspace/cards/fdn/{collector_number}/tests.py` rather than under `workspace/tests/cards/fdn/`. Colocation makes them obvious learning material attached to the card they demonstrate, and removes the directory-name collision with the host-side FDN Card Regression suite. Audited SOS grader tests remain host-side only; there is no `workspace/tests/cards/` directory. Audited FDN tests at `benchmarks/sos/data/tests/audited/fdn/{collector_number}/tests.py` exist as bench-author regression coverage — they catch engine regressions that break the canonical FDN implementations and run in bench-side CI. They are not part of agent grading (the agent is graded on SOS audited tests only) and may freely overlap in assertion content with workspace FDN tests; there is no contamination concern because the agent is not graded against either FDN suite.
- **Workspace integrity is enforced at two points, not per-file**: `stage_workspace()` performs a cheap pre-flight assertion that `benchmarks/sos/workspace/` exists and is non-empty before `copytree`. A host-side test `tests/test_workspace_structure.py` verifies the expected top-level entries (`engine/`, `cards/fdn/`, `cards/sos/`, `engine_tests/`, `conftest.py`, `test_utils.py`, `AGENTS.md`, `PROJECT_MAP.md`, `rulebook.txt`, `pytest.ini`, `.gitignore`) and fails at CI time if any are missing. This replaces the previous per-file hard-error enumeration in staging code; the canonical workspace directory is now the source of truth, and any missing file means the repo itself is broken (caught at PR-review time, not after burning agent hours).
- **Workspace ****`pytest.ini`**** is independently configured**: `benchmarks/sos/workspace/pytest.ini` sets `timeout = 300` (matching the host-side `pyproject.toml` safety net; it must be set independently because pytest does not inherit config across rootdir boundaries) and `python_files = test_*.py tests.py` so colocated FDN reference tests (`cards/fdn/fdn_{collector_number}/tests.py`) and agent-written tests (`engine_tests/test_*.py`) are both discovered. Pytest does not inherit config across rootdir boundaries, so the workspace must configure its own timeout; without this, a runaway test inside the container could hang the run or, worse, repeat PR #11-style PID 1 signal kills. [TESTING-CONVENTIONS.md](TESTING-CONVENTIONS.md) itself is not staged into the workspace — it governs bench-authored reference tests only — but the timeout safety net travels with the workspace via `pytest.ini`.
- **`AGENTS.md`**** and ****`PROJECT_MAP.md`**** have non-overlapping scopes**: `benchmarks/sos/workspace/AGENTS.md` is the orientation doc — task framing ("you are implementing SOS cards"), hard rules (card location, staged-test integrity), canonical test commands, engine-extension permission, and pointers to where to find things. `benchmarks/sos/workspace/PROJECT_MAP.md` is a directory summary — one line per top-level file/directory, nothing else. No duplication: the agent reads `AGENTS.md` at session start and consults `PROJECT_MAP.md` as a navigation lookup. `prompt.md` continues to duplicate the hard rules (card location + staged-test integrity) because the User Prompt is the only thing the agent is contractually guaranteed to read; `AGENTS.md` is convention. The `test_utils` helper API reference lives as `benchmarks/sos/workspace/test_utils.md` colocated with `test_utils.py`, not inside `PROJECT_MAP.md`.
- **Engine extension is additive — no renaming, no refactoring** [SCOPED TO SOS (V1) — Grilling 2026-08-27]: **This additive-only rule is scoped to the SOS (V1) workspace.** The HOB-generation benchmarks (hob-easy/medium/hard) **drop it** — their workspace engine is freely modifiable, with no additive-only rule and no diff policing, judged solely by the three audited dimensions against the harvested engine (see [HOB-BENCHMARKS.md](HOB-BENCHMARKS.md) → Engine rules and [SCORING.md](SCORING.md) → Agent envelope). The SOS workspace keeps this rule as part of its frozen Benchmarking-tier contract. For SOS (V1): Agents may add new methods, classes, helpers, and files inside `/workspace/engine/`, and may modify the bodies of existing functions to implement card behavior. They may NOT rename, move, or delete anything that already exists in `engine/` — no renaming functions/classes/files, no moving symbols between modules, no refactoring existing structure. Audited grader tests live host-side and `import` from `engine/` by path and symbol name; any rename/move/delete causes `ImportError` before assertions run. The flat rule (rather than enumerating a protected symbol list) keeps the prompt and `AGENTS.md` short and removes any drift risk as audited tests evolve. The staged `engine_tests/` regression suite is the agent's local proxy for "did I keep the engine importable."
- **Each benchmark set is fully self-contained**: `benchmarks/{target_set}/` is the unit of versioning. Each contains its own `workspace/` (with its own `engine/`, `cards/`, `tests/`, `AGENTS.md`, etc.) and its own `data/` (raw inputs, scoring rubric, audited grader tests). Engine baselines explicitly diverge across benchmark generations — Foundations 2 may add or remove mechanics the SOS engine never knew about, and that's the intended degree of freedom. The shared `silverquillm/` runner is benchmark-agnostic and operates on any `benchmarks/{set}/` directory by path; only the benchmark inputs change across runs. Slight engine source duplication is the price for reproducibility: a re-run of the 2026-05-24 SOS benchmark a year from now produces the same workspace against the same engine baseline regardless of where later benchmarks took the codebase. Today only `benchmarks/sos/` exists; the rule is documented now so the directory layout doesn't need to be retrofitted when Foundations 2 lands.
- **Bench-authored agent skills travel with the workspace**: `workspace/skills/{skill_name}/SKILL.md` files are copilot-format skills the bench team writes to give agents reusable subroutines (e.g. `grep-rulebook` for efficient `RULEBOOK.txt` lookups). They are part of the workspace contract and are staged into `/workspace/skills/` inside the container alongside `engine/`, `cards/`, `tests/`. Updating a skill means editing the `SKILL.md` in the bench repo and re-running.
- **Resume staging preserves prior workspace ****`.git`**: The resume staging variant copies the prior run's `workspace_final/` wholesale and overwrites only `prompt.md` and `run_manifest.json`. No `git init`. Prior commit history (host snapshots, any agent commits) is preserved as the new run's history. The Workspace Contract is unchanged — the resumed agent inherits prior compliance state. See [BENCHMARK-RUNNER.md](BENCHMARK-RUNNER.md) → Resume and ADR-008. [NEW]
- **Tracking files like ****`KEY_DECISIONS.md`****, ****`FILES_MODIFIED.json`****, ****`RUN_DECISIONS.md`****, ****`MODEL_AUDIT.jsonl`**** are agent-prompt-layer conventions, not workspace contract**: These files may appear in the Workspace as a side effect of specific agent prompt templates (e.g., a coordinator-style Pi-blind prompt). The Workspace Contract does not require, name, or specify their format. Resume detection and continuation logic that depends on these files lives in the prompt layer, not the runner; this keeps the contract image-agnostic and the runner ignorant of agent-internal scratch. If multiple agent images later converge on a common pattern, promotion to the contract can be revisited. [NEW]

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-005](../adr/ADR-005-in-place-workspace-engine-with-snapshot-fallback.md) | In-Place Workspace Engine With Snapshot Fallback |
| [ADR-006](../adr/ADR-006-engine-tests-staged-into-workspace.md) | Engine Tests Staged Into Workspace |
| [ADR-007](../adr/ADR-007-workspace-as-pre-built-directory.md) | Workspace As Pre-Built Directory |
| [ADR-008](../adr/ADR-008-resume-legs-are-independent-benchmark-runs.md) | Resume Legs Are Independent Benchmark Runs |
