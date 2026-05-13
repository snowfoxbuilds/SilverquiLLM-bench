# TODO

## Phase 9: Docker Container Flow + FDN Card Restructure

Scope: (1) Replace old adapter-based harness with Docker container system per [AGENT-CONTAINERS.md](http://agent-containers.md/) and [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) specs. (2) Restructure FDN cards to per-collector-number layout matching SOS structure.

Old harness core files ([cli.py](http://cli.py/), [config.py](http://config.py/), [strategies.py](http://strategies.py/), agent_[session.py](http://session.py/), [preflight.py](http://preflight.py/), [prompts.py](http://prompts.py/), run_[utils.py](http://utils.py/), [results.py](http://results.py/), adapters/) have already been deleted. Remaining `silverquillm/` files: card_[classifier.py](http://classifier.py/), card_[loader.py](http://loader.py/), card_[spec.py](http://spec.py/), [evaluator.py](http://evaluator.py/), post_[eval.py](http://eval.py/), [prototype.py](http://prototype.py/), [regression.py](http://regression.py/), replay/, [scorer.py](http://scorer.py/), template_[gen.py](http://gen.py/).

Reference: [CONTEXT.md](http://context.md/) for vocabulary, KEY_[DECISIONS.md](http://decisions.md/) for settled conventions, [AGENT-CONTAINERS.md](http://agent-containers.md/) for the container architecture, [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) for the host-side runner.

---

- [ ] **Delete remaining old harness code from ****`silverquillm/`**
  Detail: The following files are dead code from the adapter-based harness and have no role in the new Docker container flow. Delete them and their corresponding tests:

  - `silverquillm/card_classifier.py` — complexity tier classifier (classification now happens offline, pre-baked into card_spec.json)
  - `silverquillm/prototype.py` — prototype card selection logic (no longer needed)
  - `silverquillm/post_eval.py` — post-evaluation aggregation (replaced by new `results.py`)
  - `silverquillm/regression.py` — per-card regression runner (regression is now FDN + engine dimension in evaluator)
  - `silverquillm/scorer.py` — old 4-category scoring (replaced by 3-dimension evaluator)
  - `silverquillm/template_gen.py` — card template generation (replaced by `workspace.py` staging)
  - Keep `silverquillm/replay/` (replay validation is independent of harness)
  - Keep `silverquillm/card_spec.py` (CardSpec dataclass is reusable)
  - Keep `silverquillm/evaluator.py` (will be fully rewritten in a later item)
  - Also delete corresponding test files: `tests/test_card_classifier.py`, `tests/test_prototype.py`, `tests/test_post_eval.py`, `tests/test_regression.py`, `tests/test_scorer.py`, `tests/test_template_gen.py` (verify actual filenames via `tests/` listing before deleting).
  - Update `silverquillm/__init__.py` to remove imports of deleted modules.
  - Update tests to remove orphaned tests
  - Run `pytest --ignore=tests/audited/ -x` to verify no import breakage.
  Testability: `pytest --ignore=tests/audited/ -x` passes. No import errors. `grep -rn` for deleted module names finds zero hits in remaining source.

- [ ] **Restructure FDN cards to per-collector-number layout**
  Detail: FDN card implementations currently live in monolithic files under `cards/foundations/` (e.g. `activated_creatures.py`, `etb_creatures.py`, `simple_spells.py` — 21 files, 260+ cards). The target layout is `cards/fdn/{collector_number}/card_spec.json` + `cards/fdn/{collector_number}/card_impl.py`, matching the SOS per-card structure.

  Steps:

  1. Write a migration script `scripts/restructure_fdn_cards.py` that:
    - Reads `cards/registry.py` to get each FDN card's class name, collector number, and source file.
    - For each registered FDN card, creates `cards/fdn/{collector_number}/card_impl.py` containing only that card's class and its imports.
    - Generates `cards/fdn/{collector_number}/card_spec.json` from existing CardMetadata (name, mana_cost, type_line, oracle_text, collector_number, complexity_tier).
    - SPG cards (collector numbers 074–083 in FDN draft set) go to `cards/fdn/spg_{collector_number}/` per KEY_DECISIONS convention for multi-set collisions.
  2. Update `cards/registry.py` to import from the new per-card `card_impl.py` files instead of monolithic batch files.
  3. Delete old monolithic files under `cards/foundations/` after migration.
  4. Handle collector number collisions (KEY_DECISIONS documents `105b`, `61b` suffix convention).
  5. Verify: `pytest tests/ --ignore=tests/audited/ -x` still passes — all card tests must resolve classes from new paths.
  Testability: `cards/fdn/` has one subdirectory per FDN card. Each has `card_spec.json` + `card_impl.py`. Registry imports work. All existing card tests pass.

- [ ] **Restructure SOS cards to unified ****`cards/`**** layout**
  Detail: SOS card specs currently live under `benchmarks/sos/cards/{num}/card_spec.json`. Move them to `cards/sos/{collector_number}/card_spec.json` + `cards/sos/{collector_number}/card_impl.py` (empty template) so both sets share the `cards/{set}/` root.

  Steps:

  1. Move `benchmarks/sos/cards/{num}/card_spec.json` → `cards/sos/{num}/card_spec.json`.
  2. Generate empty template `cards/sos/{num}/card_impl.py` for each SOS card (class skeleton from card_spec, subclassing CardImpl, with `pass` methods).
  3. Non-SOS subset cards: SOA uses `cards/sos/soa_{num}/`, SPG uses `cards/sos/spg_{num}/` per KEY_DECISIONS.
  4. Update `card_loader.py` to load from `cards/{set_code}/{num}/card_spec.json`.
  5. Clean up `benchmarks/sos/cards/` (delete after migration, or keep `benchmarks/sos/fetch_data.py` if it's the Scryfall fetcher).
  Testability: `cards/sos/` has one subdirectory per SOS card. Each has `card_spec.json` + `card_impl.py` (template). Card loader resolves all cards.

- [ ] **Rewrite ****`silverquillm/card_loader.py`**** for unified card layout**
  Detail: Consolidate card loading to work with the new `cards/{set_code}/{collector_number}/` layout. Keep `card_spec.py`'s `CardSpec` dataclass as the return type.

  Functions:

  - `load_card_spec(cards_dir: Path, set_code: str, collector_number: str) -> CardSpec` — loads one card spec JSON.
  - `load_all_card_specs(cards_dir: Path, set_code: str) -> list[CardSpec]` — loads all card specs for a set, sorted by collector number.
  - `load_card_impl(cards_dir: Path, set_code: str, collector_number: str) -> Path` — returns path to card_[impl.py](http://impl.py/).
  - `is_template(card_impl_path: Path) -> bool` — checks if a card_[impl.py](http://impl.py/) is an empty template (for harvest comparison).
  Files: `silverquillm/card_loader.py`.

  Testability: Unit test with fixture card specs under `tests/fixtures/cards/`. Verify loading, sorting, missing-card error, template detection.

- [ ] **Implement ****`silverquillm/workspace.py`**** — workspace staging**
  Detail: Host-side module that builds the workspace directory before `docker run`. This is the agent's entire world — contamination control is enforced by what gets staged.

  `stage_workspace(cards_dir: Path, engine_dir: Path, output_dir: Path) -> tuple[Path, Path]` returns (workspace_path, output_path).

  Staged layout:

  ```javascript
workspace/
  prompt.md                 — single input prompt (see below)
  rulebook.md               — comprehensive rules reference
  engine/                   — full engine source (read-only reference copy)
  engine_api.md             — engine API reference doc
  base_classes.py           — CardImpl base class source
  test_utils.md             — test utility reference doc
  cards/
    fdn/{num}/              — FDN cards (filled implementations, in-context examples)
      card_spec.json
      card_impl.py
    sos/{num}/              — SOS cards (empty templates, benchmark targets)
      card_spec.json
      card_impl.py
output/                     — empty dir for progress.jsonl, stdout.log, stderr.log
  ```

  [prompt.md](http://prompt.md/) content (per [AGENT-CONTAINERS.md](http://agent-containers.md/)):

  > Implement all SOS cards in `/workspace/cards/sos/`. Each card directory contains a `card_spec.json` with the card's details and a `card_impl.py` template to fill in.

  > Use the completed FDN cards in `/workspace/cards/fdn/` as implementation examples. Refer to `rulebook.md` for detailed game rules and `engine_api.md` for the engine API.

  The prompt does NOT dictate ordering, strategy, or iteration. The agent decides.

  Reference docs (`engine_api.md`, `base_classes.py`, `test_utils.md`, `rulebook.md`) are copied from their existing locations in the repo (check `docs/` and `engine/`).

  Files: `silverquillm/workspace.py`.

  Testability: Call `stage_workspace()` → verify directory tree exists, FDN impls are non-empty, SOS impls are templates, [prompt.md](http://prompt.md/) exists, engine/ is a complete copy.

- [ ] **Create Docker images: ****`docker/opencode-tested/`**** and ****`docker/opencode-blind/`**
  Detail: Each image IS the full agent configuration. No MODE/STRATEGY env vars. Only API keys at runtime.

  `docker/opencode-tested/Dockerfile`:

  ```docker
FROM python:3.12-slim
RUN apt-get update && apt-get install -y git curl diffutils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir opencode-ai pytest
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV OPENCODE_NON_INTERACTIVE=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
  ```

  `docker/opencode-tested/entrypoint.sh`:

  ```bash
	#!/bin/bash
	set -euo pipefail
	mkdir -p /output
	# Writable engine copy — agent modifies this, original stays read-only
	cp -r /workspace/engine /workspace/engine_work
	# Build prompt: base prompt + tested-mode instruction
	PROMPT=$(cat /workspace/prompt.md)
	PROMPT="${PROMPT}

After implementing each card, write tests in a tests.py file alongside card_impl.py and iterate until they pass. Use pytest to run your tests."
	# Write started event
	echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"started\"}" >> /output/progress.jsonl
	# Trap SIGTERM for graceful shutdown on Docker timeout
	trap 'echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"timed_out\"}" >> /output/progress.jsonl; exit 143' SIGTERM
	# Invoke opencode with the full prompt, working directory is /workspace
	opencode --prompt "${PROMPT}" --dir /workspace \
	  > >(tee /output/stdout.log) \
	  2> >(tee /output/stderr.log >&2) &
	AGENT_PID=$!
	wait $AGENT_PID
	EXIT_CODE=$?
	# Write completion event
	if [ $EXIT_CODE -eq 0 ]; then
	  echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"completed\"}" >> /output/progress.jsonl
	else
	  echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"failed\", \"exit_code\": $EXIT_CODE}" >> /output/progress.jsonl
	fi
	echo $EXIT_CODE > /output/exit_code
	exit $EXIT_CODE
  ```

  `docker/opencode-blind/Dockerfile`: Identical to opencode-tested (same base, same packages).

  `docker/opencode-blind/entrypoint.sh`: Same structure but the prompt append is:

  ```bash
	PROMPT="${PROMPT}

Implement the cards from their specs alone. Do not write or run tests. Focus on reading the card_spec.json, understanding the rules text, and writing correct card_impl.py files."
  ```

  All other lines (engine_work copy, progress.jsonl, SIGTERM trap, opencode invocation, exit code) are identical.

  Image naming: `silverquillm-opencode-tested:latest`, `silverquillm-opencode-blind:latest`.

  Runtime contract:

  - `-v workspace:/workspace` (staged by host)
  - `-v output:/output` (progress, logs, exit code)
  - `-e OPENAI_API_KEY=...` `-e ANTHROPIC_API_KEY=...` (API keys only)
  - `--stop-timeout N` (Docker-level timeout)
  Note: The `opencode --prompt ... --dir ...` invocation is a placeholder — check the actual opencode CLI docs for the correct flags. The key requirements are: (1) pass the prompt as input, (2) set the working directory to `/workspace`, (3) run non-interactively. Adjust flags as needed.

  Files: `docker/opencode-tested/Dockerfile`, `docker/opencode-tested/entrypoint.sh`, `docker/opencode-blind/Dockerfile`, `docker/opencode-blind/entrypoint.sh`.

  Testability: `docker build -t silverquillm-opencode-tested:dev docker/opencode-tested/` succeeds. `docker run --rm -v /tmp/test-ws:/workspace -v /tmp/test-out:/output silverquillm-opencode-tested:dev` starts and writes `progress.jsonl` with a `started` event.

- [ ] **Implement ****`silverquillm/cli.py`**** — ****`run`**** and ****`smoke`**** commands**
  Detail: Two CLI commands using Click. The runner launches ONE container for the ENTIRE workload (not per-card). The agent handles all cards in a single long-running session.

  `silverquillm run --image <img> --cards-dir <path> --engine-dir <path> --timeout <sec>`:

  1. Call `stage_workspace(cards_dir, engine_dir, output_dir)` to build the full workspace with ALL FDN + SOS cards
  2. Call `docker run --rm -v workspace:/workspace -v output:/output <api_key_env_args> --stop-timeout <timeout> <image>`
  3. Block until container exits ([subprocess.run](http://subprocess.run/) with timeout=timeout+60 as backup)
  4. Harvest artifacts from workspace:
    - `workspace/cards/sos/*/card_impl.py` → `results/{run_name}/cards/{num}/card_impl.py`
    - `workspace/cards/sos/*/tests.py` → `results/{run_name}/cards/{num}/tests.py` (if exists)
    - `workspace/engine_work/` → diff against `workspace/engine/` → `results/{run_name}/engine_diff.patch`
    - `output/progress.jsonl` → `results/{run_name}/progress.jsonl`
    - `output/stdout.log` → `results/{run_name}/stdout.log`
    - `output/stderr.log` → `results/{run_name}/stderr.log`
  5. Determine per-card status: compare each `card_impl.py` against original template — if different, `completed`; if same, `no_output`
  6. Call `evaluator.evaluate()` on harvested results (3 dimensions)
  7. Call `results.generate_run_summary()` → `results/{run_name}/run_summary.json`
  8. On timeout: still harvest partial results, unfinished cards marked `timeout`
  Run name: `{image_short_name}_{ISO-timestamp}` (e.g. `opencode-tested_2026-05-14T10-30`).

  `silverquillm smoke --image <img>`:

  1. Stage minimal workspace: just `/workspace/prompt.md` with "Create [hello.py](http://hello.py/) that prints Hello World" and empty `/output/`
  2. `docker run` with 120s timeout
  3. Check: container exits 0, `/workspace/hello.py` exists
  4. Print PASS/FAIL
  Files: `silverquillm/cli.py`.

  Testability: Mock `subprocess.run` with a fake docker command that writes known files → verify harvest logic, verify run_summary.json structure. Real smoke test with a built image.

- [ ] **Rewrite ****`silverquillm/evaluator.py`**** — 3 evaluation dimensions**
  Detail: Complete rewrite. Three post-run scoring dimensions, all using audited tests. Agent-written tests are harvested as artifacts but NOT used for scoring.

  `evaluate(run_dir: Path, cards_dir: Path, engine_dir: Path) -> EvalResult`:

  **Dimension 1 — SOS Card Correctness:**

  For each SOS card where status=`completed`:

  - Copy agent's `card_impl.py` to a temp dir
  - Copy agent's `engine_work/` (or apply engine_diff.patch to clean engine)
  - Run `pytest tests/audited/sos/{collector_number}/tests.py` with PYTHONPATH including the modified engine
  - Record pass/fail per test → write `results/{run_name}/cards/{num}/result.json`
  **Dimension 2 — FDN Card Regression:**

  For each FDN card with audited tests:

  - Use the PRE-FILLED FDN `card_impl.py` (not agent-written — these are reference impls)
  - Use the agent's `engine_work/`
  - Run `pytest tests/audited/fdn/{collector_number}/tests.py`
  - If any fail → agent's engine modifications broke existing card behavior
  **Dimension 3 — Engine Regression:**

  - Run `pytest tests/engine/` (core engine tests, not card tests) against agent's `engine_work/`
  - If any fail → agent's engine modifications broke fundamental game mechanics
  Each dimension runs pytest in a subprocess with modified PYTHONPATH. Results aggregated into EvalResult dataclass.

  Files: `silverquillm/evaluator.py`.

  Testability: Create fixture run_dir with known card_[impl.py](http://impl.py/) (one good, one bad) and a known engine_work/ → verify per-card result.json, verify dimension aggregates.

- [ ] **Implement ****`silverquillm/results.py`**** — run summary generation**
  Detail: Pure, idempotent function that reads per-card `result.json` files and produces `run_summary.json`.

  `generate_run_summary(run_dir: Path, image_name: str) -> dict`:

  ```json
{
  "run_metadata": {
    "image": "silverquillm-opencode-tested:latest",
    "timestamp": "2026-05-14T10:30:00Z",
    "card_count": 346,
    "timeout_seconds": 7200,
    "harness_version": "<git-sha>"
  },
  "sos_card_correctness": {
    "audited_pass_rate": 0.72,
    "card_pass_rate": 0.48,
    "cards_completed": 340,
    "cards_no_output": 0,
    "cards_timed_out": 6
  },
  "fdn_regression": {
    "fdn_test_pass_rate": 0.98,
    "fdn_card_pass_rate": 0.95
  },
  "engine_regression": {
    "engine_test_pass_rate": 1.0,
    "engine_churn_lines": 342
  },
  "per_card": [
    {
      "collector_number": "1",
      "card_name": "...",
      "status": "completed",
      "audited_passed": 8,
      "audited_total": 10
    }
  ]
}
  ```

  Supports partial results (timeout/interrupt → summarizes what's available).

  Files: `silverquillm/results.py`.

  Testability: Create fixture run_dir with 3 per-card result.json → verify aggregation math, JSON schema.

- [ ] **Implement progress.jsonl protocol in entrypoints**
  Detail: Both entrypoints write `/output/progress.jsonl` for live monitoring from the host (since /output is a mounted volume, the host can `tail -f` it).

  JSONL schema:

  ```json
{"ts": "2026-05-14T10:30:00Z", "event": "started"}
{"ts": "...", "event": "card_started", "card_id": "042", "card_name": "Ajani's Response"}
{"ts": "...", "event": "card_completed", "card_id": "042"}
{"ts": "...", "event": "completed"}
  ```

  The entrypoint writes `started` before invoking the agent and `completed`/`failed` after. Card-level events are best-effort — the entrypoint can monitor `/workspace/cards/sos/*/card_impl.py` modification times via a background watcher, or the agent itself can write to progress.jsonl if the prompt instructs it to.

  On SIGTERM (Docker timeout): trap handler writes `{"event": "timed_out"}` before exit.

  Files: `docker/opencode-tested/entrypoint.sh`, `docker/opencode-blind/entrypoint.sh`.

  Testability: Run entrypoint with a mock agent → verify progress.jsonl has `started` and `completed` events.

- [ ] **Update ****`pyproject.toml`**** and ****`README.md`**** for new architecture**
  Detail:

  `pyproject.toml`:

  - Update CLI entry point to `silverquillm = silverquillm.cli:main`
  - Remove old `benchmark` entry point if present
  - Remove adapter-specific dependencies
  - Ensure `click` and `docker` (or just subprocess) are in dependencies
  `README.md`:

  - Rewrite Quickstart: `silverquillm smoke --image <img>`, `silverquillm run --image <img> --timeout 7200`
  - Document Docker image build: `docker build -t silverquillm-opencode-tested:latest docker/opencode-tested/`
  - Document 3 evaluation dimensions
  - Remove config.yaml references (image IS the config)
  - Remove adapter references
  `PROJECT_MAP.md`:

  - Update architecture diagram for container flow
  - Update file tree to show `docker/`, `cards/fdn/`, `cards/sos/`, new `silverquillm/` modules
  Files: `pyproject.toml`, `README.md`, `PROJECT_MAP.md`.

  Testability: `pip install -e ".[dev]"` succeeds. `silverquillm --help` shows `run` and `smoke`.

- [ ] **Clean up orphaned tests and verify full suite**
  Detail: Final cleanup pass after all above items.

  1. `grep -rn "from silverquillm" tests/ --include="*.py"` — find imports of deleted modules
  2. Delete orphaned test files
  3. Update `tests/conftest.py` if it references old fixtures
  4. Delete `tests/test_timeout_enforcement.py` and `tests/test_harness.py` (test old adapter/strategy code)
  5. Verify: `pytest --ignore=tests/audited/ -x` passes with 0 errors
  6. Verify: `pytest tests/audited/fdn/ -x --limit=5` passes (spot-check FDN audited tests still work with restructured card paths)
  Files: `tests/`.

  Testability: Full non-audited test suite passes. No import errors. No references to deleted modules.
