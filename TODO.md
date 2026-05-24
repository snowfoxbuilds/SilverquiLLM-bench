# TODO

## Conventions

These items must respect existing repo conventions captured in `KEY_DECISIONS.md`. Reference the relevant decision in each item's Detail where it applies:

- **`_REPO_ROOT`**** convention** — `cli.py` and `workspace.py` derive `_REPO_ROOT = Path(__file__).resolve().parent.parent`. New repo-relative paths must use this constant.
- **Collector number normalization** — `str(int(x))` at both CLI parsing and workspace staging. Phase 13 #2 must apply this when filtering `status.json`, `result.json`, etc.
- **Docker log file naming (****`.tmp`**** + ****`.log`**** copy)** — pipe-reader threads write `.tmp` files, then `runner.py` copies to `.log` after threads join. Phase 14 #1's new per-channel files should decide explicitly whether to follow this pattern or be append-only from the start.
- **Integration test CLI invocation pattern** — `[sys.executable, "-m", "silverquillm.cli", ...]` for any new integration tests.
## Phase 13: Post 05-23 Run Findings

Scope: Address the deficiencies surfaced by the `sos-2026-05-23T07-13` run on `--cards 1,7,13,44,97`. Policy: fix broken/misleading exemplars and document existing engine behavior, but do **not** pre-build engine APIs for new mechanics — the agent is expected to extend the engine itself when implementing new mechanics.

Reference: agent thinking trace in `docker/local-pi-blind/results/sos-2026-05-23T07-13/agent_stderr.log`. [Foundations Card Audit](https://www.notion.so/3606a7adc8ed8074a157db471ec4e60a) for related fdn quality work.

---

- [ ] **Wire up workspace reference material correctly**
  Detail: Today `silverquillm/workspace.py` stages four reference files at `/workspace/` (`rulebook.md`, `engine_api.md`, `base_classes.py`, `test_utils.md`) via `_RULEBOOK_SRC` (one-off, with stub fallback) and `_REFERENCE_DOCS` (dict). The 05-23 run exposed three problems:

  1. **`_RULEBOOK_SRC = "docs/rulebook.md"`**** is wrong.** That path is a hallucination from an earlier draft — `docs/` is for repo-level docs, not workspace-staging sources, and the file does not exist on `main`. The agent saw the stub fallback ("Stub — rulebook not yet generated"). The canonical rulebook is `benchmarks/sos/data/comprehensive_rules.txt`, which has now been populated with the full WotC Comprehensive Rules.
  2. **`engine_api.md`**** is misleading.** The auto-generated `docs/engine_api.md` reports `event_type: str` when the source clearly says `type[ReplacementEvent]` (see Phase 13 #4). It caused the 05-23 agent to invent a fake `game.register_replacement(...)` API. The agent should read engine source directly — modules have rich docstrings and won't go stale.
  3. **`base_classes.py`**** is a redundant rename.** It's a copy of `engine/card.py`, which is already staged via the full `engine/` tree. Two copies means the rename goes stale the moment the agent edits the engine, and it invites the wrong import path (`from base_classes import Creature` instead of `from engine.card import Creature`).
  Target state in `silverquillm/workspace.py`:

  - `_RULEBOOK_SRC = "benchmarks/sos/data/comprehensive_rules.txt"`.
  - New `_RULES_OVERVIEW_SRC = "benchmarks/sos/data/rules_overview.md"` (compact ~573-token rules skim, staged as `/workspace/rules_overview.md`).
  - `_REFERENCE_DOCS = {"test_utils.md": "docs/test_utils.md"}` — drop the `engine_api.md` and `base_classes.py` entries.
  - `_copy_reference_docs(workspace)`: remove the "write stub if source missing" fallback for the rulebook. Both rules files are now expected to exist; a missing source should be a hard error, not a silent stub.
  - `_PROMPT_TEXT`: drop the `engine_api.md` reference, add `rules_overview.md` (point the agent at it as the always-in-context rules skim) and clarify `rulebook.md` is the deep-reference. Point the agent at `engine/` source modules for API discovery — name the key ones: `engine/card.py`, `engine/events.py`, `engine/triggers.py`, `engine/replacement_effects.py`, `engine/zones.py`.
  Also update `docs/specs/WORKSPACE-CONTRACT.md` workspace-layout block to match the new staged files (drop `engine_api.md` and `base_classes.py`, add `rules_overview.md`).

  Files: `silverquillm/workspace.py` (`_RULEBOOK_SRC`, new `_RULES_OVERVIEW_SRC`, `_REFERENCE_DOCS`, `_copy_reference_docs`, `_PROMPT_TEXT` — coordinate with Phase 13 #5 and Phase 15 #2/#3 which also edit `_PROMPT_TEXT`), `docs/specs/WORKSPACE-CONTRACT.md`.

  Testability: after `silverquillm run --cards 1`, the staged workspace root contains exactly `prompt.md`, `run_manifest.json`, `rulebook.md` (full WotC text, `wc -c` > 400 KB), `rules_overview.md`, `test_utils.md`, plus the `engine/`, `tests/engine/`, and `cards/` trees. No `engine_api.md` and no `base_classes.py`. `grep -i 'engine_api\|base_classes' workspace/prompt.md` returns nothing.

- [ ] **`--cards`****-aware status / summary / postmortem plumbing**
  Detail: When a run is invoked with `--cards 1,7,13,44,97`, the run artifacts should reflect *that selection*, not the entire set. Concrete gaps observed in `sos-2026-05-23T07-13/`:

  1. **`status.json`**: lists all 339 set cards, with 334 marked `no_output`. Should list only the 5 requested cards.
  2. **`run_summary.json`**: not written at all for partial runs. Should be written regardless of selection size, and must include the `card_filter` field (already SETTLED in [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) → Filtered runs). The manifest scope stays unchanged — only `timeout_seconds` and `deadline_utc`.
  3. **Per-card ****`result.json`**** and ****`postmortem.jsonl`**: not produced for the 5 completed cards. The post-eval / scoring step did not run. Should run on every completed card in the `--cards` set.
  Files: `silverquillm/cli.py` — specifically `_harvest_results()` (does not currently receive `card_filter`; must accept and thread it through from `run()`), `_write_card_statuses()` (currently iterates ALL specs from `load_all_card_specs(cards_dir, "sos")`; must be scoped to the filter), and the two existing stubs `_evaluate_results()` and `_generate_run_summary()` which currently just print `"TODO: ..."`. Also any scoring/post-eval module these stubs eventually delegate to. Reuse `str(int(cn))` collector-number normalization per `KEY_DECISIONS.md` → "Collector number normalization" when comparing filter values to spec collector numbers.

  Testability: Run `silverquillm run --cards 1,7 --image silverquillm-local-pi-blind:latest`. Confirm `status.json` has exactly 2 entries, `run_summary.json` exists, both card dirs have `result.json` and `postmortem.jsonl`.

- [ ] **Fix broken/misleading ****`fdn/`**** implementations**
  Detail: The Foundations exemplars set bad precedent that blind-mode agents copy. Known offenders from the 05-23 trace:

  1. **`fdn_194 EtaliPrimalStorm`**: bypasses the stack and `cast_spell` pipeline by manually calling `on_resolve`. The engine *does* support proper free-casts via the existing replacement/cast infrastructure — Etali is just wrong. Rewrite to respect the stack.
  2. **Audit sibling fdn cards** for similar shortcuts (manual `on_resolve`, direct zone mutation bypassing events, ad-hoc `_omniscience_active`-style flags used for one-shot effects). Cross-reference with [Foundations Card Audit](https://www.notion.so/3606a7adc8ed8074a157db471ec4e60a) and rewrite anything that takes shortcuts around existing engine capabilities.
  3. **Do NOT add new exemplars for mechanics fdn doesn't naturally have** (e.g. don't fabricate a split-card example if Foundations has no split cards). The agent owns new-mechanic implementation.
  Files: `cards/fdn/fdn_194/card_impl.py` and any other audit-flagged cards (note: cards live under `cards/fdn/` at the repo root, not under `benchmarks/`).

  Testability: For each rewritten card, an interaction test where a Counterspell-style effect can target the free-cast spell on the stack should now succeed where it previously failed (the spell goes through the stack).

- [ ] **Complete the event-type strings→classes migration**
  Detail: The engine has already migrated from raw-string event types to typed event classes. The source on `main` declares `event_type: type[ReplacementEvent]` in `engine/replacement_effects.py` and `event_type: type[TriggeredEvent]` in `engine/triggers.py`; `engine/events.py` defines the full hierarchy (`MoveToGraveyardReplacementEvent` ← `CreatureDiesReplacementEvent` / `SacrificeReplacementEvent` / `PermanentDestroyedReplacementEvent`, plus `CreateTokenReplacementEvent`, `AddCounterReplacementEvent`, and the parallel `*TriggeredEvent` family). The one-shot migration script `migrate_events.py` holds the canonical string→class mapping (`STRING_TO_REPLACEMENT_CLASS`). Two stragglers still teach the old style:

  1. **`cards/fdn/fdn_244/card_impl.py`** still registers with raw strings: `for event_type in ("move_to_graveyard", "creature_dies", "sacrifice"):`. Rewrite to use the typed classes. Note that `CreatureDiesReplacementEvent` and `SacrificeReplacementEvent` both subclass `MoveToGraveyardReplacementEvent`, so a single registration against the parent covers all three via subclass-dispatch — pick whichever matches the card's intended semantics. Other fdn cards already use the new pattern correctly (e.g. `fdn_216` registers `CreateTokenReplacementEvent` / `AddCounterReplacementEvent` directly); use those as the reference exemplar.
  2. **`docs/specs/CARD-INTERFACE.md`** "Replacement Effects" example shows `event="creature_dies"` and a `game.register_replacement(...)` API that does not exist in the engine. The real API is `game.replacement_manager.register(ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=..., condition=..., replacement=..., controller=...))`. Rewrite the example to match the migrated, actually-existing API. This spec is no longer staged into the workspace (per Phase 13 #1, only the two rules files and `test_utils.md` ship), but it's the first thing new contributors read and any future doc-generation tooling will pull from it — leaving the wrong example in encodes the wrong mental model.
  Note: `docs/engine_api.md` is also stale (reports `event_type: str`), but Phase 13 #1 drops it from the workspace, so fixing the auto-generator is out of scope for this item. If `engine_api.md` is ever restored to the workspace, regenerating it correctly becomes prerequisite work.

  Why this matters: typed event classes enable subclass-based registration (a handler on `MoveToGraveyardReplacementEvent` fires for `CreatureDiesReplacementEvent` too, per the documented inheritance semantics in `engine/events.py`). Raw strings can't express that — leaving stragglers around encodes the wrong mental model.

  Files: `cards/fdn/fdn_244/card_impl.py`, `docs/specs/CARD-INTERFACE.md`. Reference: `migrate_events.py::STRING_TO_REPLACEMENT_CLASS` for the canonical mapping, `engine/events.py` for the full class hierarchy, `cards/fdn/fdn_216/card_impl.py` for a correctly-migrated example.

  Testability: After the fix, `grep -rn "event_type *= *['\"]" cards/fdn/ docs/specs/` should return zero matches (the migration script `migrate_events.py` can be re-run as a verification pass). Engine regression tests on `fdn_244` should pass unchanged after the rewrite.

- [ ] **Add engine-extension permission line to the agent prompt**
  Detail: Add to the user prompt (the one shipped to the agent container):

  > "You are expected to make changes to the engine to implement new mechanics. The existing code base may not be perfect, you are free to make changes that don't break current behavior."

  This makes explicit what the benchmark already grades for (Cat4 Engine Extension Quality) and reduces the chance the agent treats the engine as immutable and resorts to fdn-style hacks. Pair with the broken-fdn cleanup above so the precedent the agent sees is actually good.

  Files: `silverquillm/workspace.py` — the user prompt lives in the module-level `_PROMPT_TEXT` constant (not a separate template file). Append the new sentence to that string. The `_prompt_text()` helper already handles `--cards`-filter substitution; the new sentence should be in the base template so both filtered and unfiltered runs include it. Optional follow-up (not required for this item): extract `_PROMPT_TEXT` to a real template file under `silverquillm/templates/` for easier editing.

  Testability: Grep the staged `workspace/prompt.md` of a new run for the new sentence. Run a card that requires a new mechanic (e.g. sos_1 cast-from-graveyard) and confirm the agent's thinking trace shows it considering engine changes rather than only fdn pattern-matching.

## Phase 14: Telemetry Improvements

Scope: Improve live and post-run command-line observability without touching the 60-second Git snapshot cadence. The Git snapshot loop (audit/recovery) stays at 60s as specified in [RUN-ARTIFACTS-AND-TELEMETRY.md](http://run-artifacts-and-telemetry.md/). All work below is purely command-line / terminal-output telemetry.

Reference: [RUN-ARTIFACTS-AND-TELEMETRY.md](http://run-artifacts-and-telemetry.md/) → Terminal channels (per-channel file mapping) and Decisions ("v1 includes a tabbed post-run log viewer"). Item 1 below implements the per-channel files; item 2 implements the tabbed viewer over those files. (Historical context, now superseded: *"A separate post-run **`logs --run`** viewer is deferred for v1"* — item 2 below lifts that deferral.)

---

- [ ] **Add fast-tier (1 Hz) command-line telemetry**
  Detail: Introduce a second telemetry tier that runs at 1 Hz (or on FS events via `watchdog`/`inotify` for zero-poll). Reads only cheap signals — no Git operations, no full-workspace stat sweeps. Sources:

  1. **Tail ****`/output/progress.jsonl`** — append-only file the agent writes when it completes a card. Emit each new line as a `[progress]` event.
  2. **Tail ****`/output/system.log`** — agent's free-form status. Emit new lines as `[system]` events.
  3. **`stat`**** mtimes on ****`workspace/cards/*/card_impl.py`**** and ****`workspace/engine/*.py`** — detect in-flight edits between snapshot intervals. Emit a `[edit]` event when an mtime advances, with the path. Cheap because we only stat a known small set of paths.
  4. **Do NOT trigger Git snapshots from this tier.** The 60s snapshot loop is independent and unchanged.
  5. **One append-only file per channel on the host.** Each telemetry stream writes to its own file under the run directory — the substrate the tabbed log viewer reads. Channel → file mapping:
    - `[runner]` → `runner.log` (runner-internal messages)
    - `[snapshot]` → `snapshot_telemetry.jsonl` (already exists)
    - `[stdout]` → `docker_stdout.log` (already exists)
    - `[stderr]` → `docker_stderr.log` (already exists)
    - `[error]` → `runner_errors.log`
    - `[progress]` → `progress.jsonl` (mirrored from `/output/progress.jsonl` to host)
    - `[edit]` → `fast_telemetry.jsonl`
    - `[system]` → `system.log` (mirrored from `/output/system.log` to host)
  Files: `silverquillm/runner.py` (new fast-tier loop alongside the existing snapshot loop), `silverquillm/telemetry.py` (or wherever the channel-labeled streaming lives).

  Testability: Run a real benchmark. Touch `workspace/cards/sos_1/card_impl.py` inside the container; confirm a `[edit]` line appears in the runner terminal within ~1s. Append a line to `/output/progress.jsonl`; confirm a `[progress]` line appears within ~1s. Confirm `snapshot_telemetry.jsonl` is still written every 60s with unchanged content.

- [ ] **Tabbed log viewer (live + archived modes)**
  Detail: A single CLI binary that opens a one-panel, tab-per-channel terminal viewer over the run's per-channel log files. Works during a live run (tails files) and for finished runs (static history with the same UX). Supersedes the earlier separate `logs --run` viewer, channel-toggles, and multi-pane dashboard items — the file-backed substrate from the item above makes one design serve both modes.

  Invocation:

  ```javascript
silverquillm logs --run sos-2026-05-23T07-13              # auto-detect: live if active, archived if done
silverquillm logs --run sos-2026-05-23T07-13 --live       # explicit live (errors if run not active)
silverquillm logs --run sos-2026-05-23T07-13 --archived   # explicit static mode
  ```

  Layout: single panel + tab bar + status footer.

  ```javascript
┌──────────────────────────────────────────────────────────┐
│ [1] runner  [2] snapshot  [3] stdout  ▶[4] stderr◀  [5] error  ...  │  tab bar
├──────────────────────────────────────────────────────────┤
│  (last N lines of the active tab's file)                          │
│  ...live appends arrive as the file grows (live mode)...          │  panel
├──────────────────────────────────────────────────────────┤
│ TAIL  sos-2026-05-23T07-13  q quit  ↑↓ scroll  End live          │  status footer
└──────────────────────────────────────────────────────────┘
  ```

  Hotkeys:

  - `1`–`8`: switch active tab (re-render history from the channel's file).
  - `↑` / `↓` / `PgUp` / `PgDn` / `Home`: enter SCROLLBACK mode (freeze viewport; new appends do not move the view but bump an unread badge on the active tab).
  - `End` / `G`: return to TAIL mode (auto-scroll to bottom on new lines).
  - `q`: quit the viewer. In live mode the run continues; only the viewer exits.
  Implementation mechanics:

  1. **Take over the terminal with the alternate screen buffer on entry, restore on exit.** Restoration must run on SIGINT, SIGTERM, normal quit, and uncaught exceptions — a broken teardown leaves the user's terminal unusable. This is the single highest-priority correctness detail.
  2. **Raw mode** (termios cbreak) for single-keystroke capture. Restore on exit alongside the alternate screen.
  3. **On tab switch**: stop the previous tail thread, open the new channel's file, seek to `end - viewport_lines` (or to 0 if the file is shorter), render the window, then start a new tail thread (inotify on Linux with polling fallback).
  4. **TAIL mode**: new appends append at the bottom; scroll up by one line when the panel is full.
  5. **SCROLLBACK mode**: viewport is a line offset into the file; new appends do not move the viewport but increment an unread counter for the active tab's tab-bar badge. `End` / `G` clears the badge and returns to TAIL.
  6. **Unread badges on inactive tabs**: each non-active tab shows a count badge (e.g. `[4] stderr (12)`) when new lines have arrived since the user last viewed it. Cleared on switching to that tab.
  7. **Resize**: handle `SIGWINCH`; re-clamp viewport to terminal size; re-render.
  8. **Non-TTY fallback**: if stdout is not a TTY (CI, piped), `logs` falls back to interleaved plain streaming over all per-channel files with channel labels. Live mode still works; just no interactive UX.
  Decoupling from log writing:

  - The viewer is **read-only over files**. The runner writes per-channel files exactly as the previous item specifies, whether or not anyone is viewing them. Running the viewer or not has zero impact on saved artifacts.
  Library choice:

  - Use `rich` for rendering primitives (table for tab bar, panel for content, footer). Avoid `textual` — the single-panel design does not need its app framework, and `rich` alone keeps the dependency surface smaller.
  - Fall back to raw ANSI if `rich` proves cumbersome for the alternate-screen + raw-mode pattern.
  Files: `silverquillm/cli.py` (new `logs` subcommand), `silverquillm/logs_viewer.py` (new module: terminal control, tab bar, viewport, file tailing).

  Testability:

  - Unit tests on viewport math (seek-to-end-N, scroll up/down, resize clamping).
  - Integration: launch the viewer in a pty against a fixture run directory; programmatically send keystrokes (`1`, `2`, `↑`, `End`, `q`); assert rendered output matches expectation per step.
  - Manual: open a live run; tab between channels; confirm history loads instantly on each switch; confirm new appends arrive within ~1s on TAIL; confirm SCROLLBACK freezes correctly; confirm `q` restores the terminal cleanly; confirm SIGINT (Ctrl-C) also restores the terminal cleanly.
  Estimated effort: 1–1.5 days. Single largest risk is reliable terminal-state teardown across SIGINT / crash / exit paths.

## Phase 15: Workspace Contract & Triage Improvements

Scope: Reduce time-to-diagnosis on completed runs and tighten the agent's feedback loop without leaking SOS card tests. The SOS Card Correctness tests remain hidden — only engine and FDN regression tests are staged into the workspace.

Reference: [WORKSPACE-CONTRACT.md](http://workspace-contract.md/), [RUN-ARTIFACTS-AND-TELEMETRY.md](http://run-artifacts-and-telemetry.md/).

---

- [ ] **Propagate card names into slow-cadence artifacts; terminal resolves at print time**
  Detail: Most artifacts reference cards by ID only (`sos_1`, `sos_7`). Human triage is faster with names inline. Add `card_name` alongside `card_id` in slow-cadence artifacts and resolve names at print time for live terminal output. `snapshot_telemetry.jsonl` stays IDs-only per the SETTLED scope carve-out in [RUN-ARTIFACTS-AND-TELEMETRY.md](http://run-artifacts-and-telemetry.md/) (high-cadence file; lean payloads).

  Changes:

  1. **`progress.jsonl`** entries: add `card_name` field alongside `card_id`.
  2. **`status.json`**: each card entry gains a `card_name` field.
  3. **`result.json`** (created by Phase 13 #2): include `card_name`. [BENCHMARK-RUNNER.md](http://benchmark-runner.md/)'s example already shows this.
  4. **Live ****`[snapshot]`****, ****`[progress]`****, ****`[runner]`**** terminal channels**: resolve card names from `card_spec.json` at print time for any line that mentions a card ID. Terminal stays readable, JSONL stays lean.
  5. **`snapshot_telemetry.jsonl`**: unchanged — stays IDs-only.
  Source of truth: the card metadata table the runner already consults to stage `cards/sos/`. Plumb it through to the slow-cadence artifact writers and the terminal-print layer.

  Files: `silverquillm/runner.py`, scoring/post-eval pipeline, `silverquillm/telemetry.py`.

  Testability: Run any benchmark with `--cards 1,7`. Confirm `status.json` entries contain `"card_name": "Dawning Archaic"`. Confirm `progress.jsonl` lines include the name. Confirm `snapshot_telemetry.jsonl` events have only `card_id`, no `card_name`. Confirm live `[snapshot]` lines print "sos_1 Dawning Archaic" while the underlying JSONL line has only `"sos_1"`.

- [ ] **Agent-authored ****`decisions.md`**** artifact**
  Detail: Add `decisions.md` to the workspace contract as a first-class artifact the agent is expected to maintain. Purpose: structured human-readable record of *why* the agent made each non-obvious implementation choice and *what it knows it punted on*. Massively reduces triage time vs. reading stderr stream-of-consciousness.

  Expected structure (enforce via prompt, not schema):

  ```javascript
# Decisions
## sos_1 Dawning Archaic
- Needed: cast spell from graveyard without paying.
- No documented API found; reused `_omniscience_active` flag from fdn_161 (semantically wrong for one-shot but no alternative).
- BLOCKED: proper `cast_for_free(card, from_zone=...)` API would clean this up.
## sos_13 Emeritus of Truce // Sands of Time
- No split-card precedent in fdn/. Modeled after MTG split-card pattern manually.
- ...
  ```

  Update the prompt to require the agent to maintain `decisions.md` as it works. Update [WORKSPACE-CONTRACT.md](http://workspace-contract.md/) to list it as part of the workspace layout. The agent already documents this in stderr — making it a structured artifact just surfaces what's already happening.

  Files: `silverquillm/workspace.py` (extend the `_PROMPT_TEXT` module-level constant with the maintain-`decisions.md` instruction — same constant Phase 13 #5 touches), `docs/specs/WORKSPACE-CONTRACT.md` (list `decisions.md` in the workspace layout), [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) (staging step creates an empty `decisions.md` for the agent to fill).

  Testability: After a run, `decisions.md` exists in `workspace_final/` and contains an entry per attempted card.

- [ ] **Stage engine tests into the workspace (per ADR-006)**
  Detail: Agents extending the engine had no local way to validate engine changes (the silent-regression failure mode that surfaced in the 05-23 run). Stage the Cat3 Engine Regression test suite into the workspace so the agent can run it locally. FDN and SOS card tests remain hidden.

  Staging:

  1. **`workspace/tests/engine/`** — mirror of `tests/engine/` from the host repo.
  2. **FDN card tests are NOT staged.** Agents should not be modifying FDN reference implementations; re-running FDN tests during the run would waste budget on non-target cards.
  3. **SOS card tests are NOT staged.** Cat1 is the benchmark target; must remain memorization-resistant.
  Grading authority (from ADR-006):

  1. The runner uses its host-repo copy of `tests/engine/` for grading, not the staged workspace copy.
  2. The agent must NOT modify the staged tests. Modifying a workspace test to make it pass produces a false-positive local signal without affecting the score — strictly worse than no signal.
  3. Enforce via prompt, not file permissions. The no-modify rule is now in [WORKSPACE-CONTRACT.md](http://workspace-contract.md/)'s Agent prompt rule section.
  Why engine tests are safe to stage (and SOS/FDN are not):

  - Engine tests exercise generic engine APIs (mana, stack, combat, state-based actions). Any correct engine must implement these — "memorizing the test" largely reduces to "implementing the engine correctly."
  - SOS tests grade benchmark targets directly; staging them would defeat the benchmark.
  - FDN tests grade reference implementations the agent should not be touching anyway.
  Files: `silverquillm/workspace.py` — both the staging logic (add a new step copying `tests/engine/` into `workspace/tests/engine/`) and the `_PROMPT_TEXT` module-level constant (append the no-modify rule for staged tests, propagating [WORKSPACE-CONTRACT.md](http://workspace-contract.md/)'s rule). Coordinate with Phase 13 #5 and Phase 15 #2, which also edit `_PROMPT_TEXT`.

  Testability: After staging, `ls workspace/tests/engine/` succeeds. Confirm `ls workspace/cards/fdn/fdn_001/tests.py` and `ls workspace/cards/sos/sos_1/tests.py` do NOT exist. Editing `workspace/tests/engine/test_*.py` and re-running grading produces unchanged scores (runner uses host copy). Grep the staged `workspace/prompt.md` for the no-modify rule.
