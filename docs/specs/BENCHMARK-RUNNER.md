Status: SETTLED

Last updated: 2026-04-28

# Benchmark Runner

Orchestration harness for the end-to-end benchmark.

## Context

The runner feeds cards to agents, collects implementations and tests, runs evaluation, and records results. It enforces contamination controls and tracks cost metrics.

## Design

### Architecture

```mermaid
graph TD
    A["Card Spec"] --> B["Step 1: Blind Implementation"]
    B --> C["Save blind_impl.py"]
    B --> D["Step 2: Write Tests + Update Code"]
    D --> E{"Round < 3?"}
    E -->|Yes| F["Run tests, feed results back"]
    F --> D
    E -->|No / All pass| G["Save tested_impl.py + tests.py"]
    G --> H["Eval 1: Self-eval"]
    G --> I["Eval 2: Cross-eval"]
    G --> J["Eval 3: Audited eval"]
```

### Runner Configuration

```yaml
name: "SOS Benchmark Run"
set_code: "SOS"
model_name: "claude-sonnet-4-20250514"
model_provider: "anthropic"
max_context: 200000
temperature: 0.0
agent:
  adapter: "opencode"              # one of: opencode | claude_code | aider | pi
  max_test_rounds: 3
  timeout_per_card: 300
  disable_web_search: true
card_specs_dir: "benchmarks/sos/cards"
engine_docs_path: "docs/engine_api.md"
output_dir: "benchmarks/sos/results"
```

### Multi-Agent Support

The runner supports multiple agent adapters via a pluggable `AgentAdapter` base class. Each adapter translates the runner's prompts and workspace into the agent tool's native interface.

```python
class AgentAdapter(ABC):
    """Base class for agent tool adapters."""
    @abstractmethod
    def run(self, prompt: str, workspace: Path, timeout: int) -> AgentRunResult: ...
    @abstractmethod
    def get_session_log(self) -> str: ...
```

**Supported adapters (v1):**

| Adapter | Tool | Tool-calling | Notes |
| --- | --- | --- | --- |
| `opencode` | OpenCode | Required (OpenAI-compatible) | `opencode run [message]`; config via `opencode.json` |
| `claude_code` | Claude Code | Native | Anthropic's CLI agent; `claude -p [message]` |
| `aider` | Aider | Not required (text-based edits) | Best for models without tool-calling (e.g. MiniMax via llama.cpp) |
| `pi` | Pi ([pi.dev](http://pi.dev/)) | Required | General-purpose coding agent |

The adapter is selected by `agent.adapter` in config. Each adapter captures stdout/stderr and structures it into the postmortem log (see Per-Round Logging below).

### Workspace Model: Persistent Engine per Run

A single benchmark run processes cards **sequentially** with a **shared, writable engine** that accumulates the agent's modifications across cards. Each run starts from the same base engine, so different agents/models are comparable.

**Per-run engine lifecycle:**

1. Run starts → copy `engine/` to a persistent run-level engine directory (writable)
2. Card 1 workspace created → symlinks or copies the run engine into workspace
3. Agent implements card 1 → may modify engine files (e.g., add a new mechanic)
4. Card 1 completes → engine changes are **committed back** to the run-level engine
5. Card 2 workspace created → starts with the engine as modified by card 1
6. …repeat for all cards…
7. Run ends → final engine state saved as an artifact alongside results
**Why persistent**: Cards in the target set may require mechanics not in the base engine (e.g., Ward, Magecraft). The agent must extend the engine to implement them. A good agent writes **generic mechanics** that work for future cards — not one-off hacks. This measures architectural quality and forward thinking.

**Regression check**: After each card completes, the runner re-runs all previous cards' tests against the modified engine. Any failure = regression. Regressions are recorded per card and penalized in scoring (see [SCORING.md](http://scoring.md/)).

**Card ordering**: Cards are sorted by complexity tier (trivial → simple → medium → complex → expert) so the agent builds up engine capabilities gradually. Within a tier, cards are sorted by collector number for determinism.

### Agent Context

Files provided to the agent in each card's workspace:

- `card_spec.json` — Card data (name, mana cost, type line, oracle text)
- `engine_api.md` — Game engine API reference
- `engine/` — **Writable** copy of the game engine (persistent across cards within a run)
- `base_classes.py` — Card base classes (convenience copy from engine/)
- `test_utils.md` — Test utilities documentation (always available; referenced in Step 2 prompt)
- `test_utils.py` — Test utilities module (always available; agent is instructed not to write tests in Step 1)
- `template.py` — Skeleton with standardized class name and imports
- `rules_overview.md` — Brief MTG rules overview + best practices for grepping the full rules
- `comprehensive_rules.txt` — Full MTG comprehensive rules (available for grepping; agents manage their own context budget)
- `foundations/` — Browsable codebase of Foundations card implementations (read-only, not bulk-loaded)
Context limit: 200K tokens. Agent manages its own context budget.

Not provided (contamination controls): no target set implementations, no XMage Java source, no internet, no other agents' work.

**Engine modification rules**: The agent may add new files to `engine/` or modify existing ones. The prompt instructs the agent that all previous cards' tests will be re-run after each card, so engine changes must not break existing functionality.

### Cross-Evaluation Compatibility

Every card uses a standardized class name and module path from `template.py`:

```python
from silverquillm.engine import *
from silverquillm.cards.base import CardImpl

class StrixhavenProdigy(CardImpl):
    """Implementation of Strixhaven Prodigy."""
    ...
```

The runner swaps implementations by replacing the .py file. Tests import from `card_impl`, so any agent's code can be dropped in.

### Step 1: Blind Implementation Prompt

```javascript
You are implementing a Magic: The Gathering card for the SilverquiLLM-bench game engine.

Card: {card_name}
Mana Cost: {mana_cost}
Type: {type_line}
Rules Text: {oracle_text}

Implement this card by completing the class in template.py.
You have access to:
- engine_api.md (game engine API reference)
- engine/ (game engine source — you may extend it if this card needs mechanics not yet supported)
- base_classes.py (card base classes)
- rules_overview.md (brief rules overview + grep best practices)
- comprehensive_rules.txt (full rules, available for grepping)
- foundations/ (browse working card implementations as reference)

Write your implementation to `blind_impl.py`.
If you need to add or modify engine files, do so — but all previous cards' tests
will be re-run, so your engine changes must not break existing functionality.
Do not rename the class. Do not write tests.
```

### Step 2: Test-Informed Implementation Prompt

```javascript
Now write a comprehensive test suite for your implementation of {card_name}.

Constraints:
- You MUST use the test_utils helpers (create_game, set_board_state, cast_spell, etc.)
  See test_utils.md for the full API.
- Maximum 30 tests per card. Focus on quality over quantity.
- Tests must import from card_impl (e.g. `from card_impl import {ClassName}`)

Test for:
- Basic functionality (correct stats, mana cost, card types)
- Core abilities working correctly
- Edge cases (no valid targets, empty board, etc.)
- Interaction with game rules (stack, priority, state-based actions)

Save your updated implementation to `tested_impl.py`.
Save your tests to `tests.py`.
You may also modify engine/ files if needed — but all previous cards' tests
will be re-run, so engine changes must not break existing functionality.
You have up to 3 rounds to iterate on both tests and code.
```

### Evaluation Phase

1. **Self-eval**: Run blind_[impl.py](http://impl.py/) and tested_[impl.py](http://impl.py/) against agent's own [tests.py](http://tests.py/)
2. **Cross-eval**: Run all agents' implementations against all other agents' tests
3. **Audited eval**: Run all implementations against human-curated gold-standard tests
### Result Record

```json
{
    "card_id": "sos-042",
    "agent": "claude-sonnet-4",
    "complexity_tier": "medium",
    "implementation": {
        "blind_tokens": {"input": 8200, "output": 4250, "total": 12450},
        "blind_runtime_ms": 45200,
        "blind_peak_context": 52000,
        "tested_tokens": {"input": 18400, "output": 10400, "total": 28800},
        "tested_runtime_ms": 120500,
        "tested_peak_context": 98000,
        "test_iterations": 2,
    },
    "self_eval": {
        "blind": {"passed": 5, "failed": 3, "total": 8},
        "tested": {"passed": 8, "failed": 0, "total": 8}
    },
    "cross_eval": {"agent_b_tests": {"...": "..."}, "agent_c_tests": {"...": "..."}},
    "audited_eval": {
        "blind": {"passed": 6, "failed": 6, "total": 12},
        "tested": {"passed": 10, "failed": 2, "total": 12}
    }
}
```

### Contamination Controls

1. **No web access** — OpenCode `deny` permission on webfetch and network commands
2. **Fresh workspace per card** — New temp directory per card, but engine state carries forward within a run
3. **New set cards** — SOS released 2026-04-24; too new for LLM training data or XMage implementation
4. **No cross-agent leakage** — Each agent/model gets its own run with a fresh engine copy. Agents never see other agents' engine modifications or implementations
5. **Engine regression gate** — After each card, all previous cards' tests are re-run. Engine modifications that break earlier cards are detected and penalized
### Per-Round Logging & Postmortem

Since agent export tools (e.g. `opencode export`) are unreliable, the runner captures structured logs per round for every card. These logs are the primary source for debugging and postmortem analysis.

**What is captured per round:**

- Agent stdout/stderr (full text, streamed in real-time)
- Agent thinking/reasoning traces (if the model emits them)
- Files created or modified in workspace (diff format)
- Test results (pytest output, pass/fail counts, assertion messages)
- Timing: round start, agent finish, test finish
- Token usage (if reported by the agent tool)
**Postmortem log file** (`postmortem.jsonl`): One JSON line per event, stored per card:

```json
{"ts": "2026-05-07T10:01:23Z", "round": 1, "phase": "blind", "event": "agent_start", "prompt_hash": "abc123"}
{"ts": "2026-05-07T10:02:45Z", "round": 1, "phase": "blind", "event": "agent_output", "stream": "stdout", "text": "Thinking: I need to implement..."}
{"ts": "2026-05-07T10:03:10Z", "round": 1, "phase": "blind", "event": "agent_finish", "exit_code": 0, "runtime_ms": 107200}
{"ts": "2026-05-07T10:03:11Z", "round": 1, "phase": "blind", "event": "file_diff", "path": "card_impl.py", "diff": "+class EagerGlyphmage(Creature):..."}
{"ts": "2026-05-07T10:03:15Z", "round": 1, "phase": "test", "event": "pytest_result", "passed": 5, "failed": 3, "output": "..."}
```

**Artifacts per card** (updated layout):

```javascript
cards/{card_id}/
├── blind_impl.py
├── tested_impl.py
├── tests.py
├── result.json
├── postmortem.jsonl          # Full structured log for debugging
├── agent_thoughts.md         # Extracted reasoning traces (human-readable)
├── iterations/
│   ├── round_1/
│   │   ├── impl.py
│   │   ├── tests.py
│   │   └── pytest_output.txt
│   └── round_2/ ...
└── audited_tests.py          # Gold-standard tests (if audited)
```

The `agent_thoughts.md` file is auto-generated from `postmortem.jsonl` by extracting reasoning/thinking blocks from agent output. This gives a human-readable narrative of the agent's approach for each card.

### Agent Setup Questioning

Agents may encounter issues with the workspace setup (missing files, unclear engine API, card spec ambiguities). Rather than silently failing or hallucinating, agents can emit structured **setup questions** via a `setup_questions.json` file in the workspace.

```json
[
  {
    "type": "missing_file",
    "description": "test_utils.py referenced in prompt but not found in workspace",
    "severity": "blocking"
  },
  {
    "type": "ambiguous_spec",
    "description": "Card rules text says 'counter target spell' but engine_api.md has no counter_spell() method",
    "severity": "warning"
  },
  {
    "type": "engine_gap",
    "description": "No API for 'exile from graveyard' — only exile() from battlefield exists",
    "severity": "blocking"
  }
]
```

**Schema fields:**

- `type`: one of `missing_file`, `ambiguous_spec`, `engine_gap`, `mechanic_not_found`, `import_error`, `other`
- `description`: free-text explanation of the issue
- `severity`: `blocking` (cannot proceed) or `warning` (proceeded with best guess)
The runner checks for `setup_questions.json` after each agent run. Blocking questions are logged and the card is marked `status: "setup_error"`. Warning questions are logged in the postmortem but don't halt execution. Aggregated questions across all cards surface systemic issues (e.g. a missing engine method needed by many cards).

### Error Handling

| Error | Handling |
| --- | --- |
| Agent timeout | Record "timeout"; count as all tests failed |
| Syntax/import error | Feed to correction round |
| Runtime error in tests | Record which tests errored; count as failures |
| No output | Record "no_output"; all tests failed |
| Wrong files modified | Discard changes; record "violation" |

### Output Artifacts

All set-specific artifacts live under `benchmarks/{set_code}/` so future sets get a clean directory:

```javascript
benchmarks/sos/
├── data/
│   ├── sos.json                  # Scryfall card data cache
│   ├── sos_classified.json       # Complexity tier classifications
│   ├── comprehensive_rules.txt   # Pinned MTG rules for this expansion
│   └── rules_overview.md         # Compact rules summary for agent context
├── cards/
│   ├── 001/
│   │   └── card_spec.json        # Per-card spec for agents
│   └── ...
├── prototype_cards.json          # Selected prototype cards + rationale
├── prototype_gaps.md             # Engine gap analysis
└── results/
    └── {run_name}/               # One folder per run (e.g. "claude-sonnet-4_2026-04-28T18-30")
        ├── config.yaml            # Copy of the run config
        ├── summary.json           # Aggregate stats for this run
        ├── cross_eval_matrix.json # Cross-eval results (if multi-agent)
        ├── leaderboard.md         # Scored leaderboard for this run
        └── cards/
            ├── sos-001/
            │   ├── blind_impl.py
            │   ├── tested_impl.py
            │   ├── tests.py
            │   ├── iterations/
            │   ├── result.json
            │   └── audited_tests.py  # Gold-standard tests (if audited)
            └── ...
```

Run name defaults to `{model_name}_{ISO-timestamp}` (e.g. `claude-sonnet-4_2026-04-28T18-30`). Each run is self-contained with its config and per-card artifacts. Cross-run aggregates (multi-model leaderboard, combined cross-eval matrix) live directly in `benchmarks/sos/results/`:

```javascript
benchmarks/sos/results/
├── leaderboard.md                 # Combined leaderboard across all runs
├── cross_eval_matrix.json         # Cross-eval across runs (if multi-model)
├── summary.json                   # Aggregate stats across all runs
├── claude-sonnet-4_2026-04-28T18-30/
│   ├── config.yaml
│   ├── summary.json               # Per-run stats
│   └── cards/ ...
├── gpt-5_2026-04-29T09-15/
│   ├── config.yaml
│   ├── summary.json
│   └── cards/ ...
└── ...
```

Set-agnostic files stay at top level: `docs/` (engine_[api.md](http://api.md/), test_[utils.md](http://utils.md/)), `benchmark/` (runner package code). Rules are pinned per set since comprehensive rules change per expansion.

### Cost Tracking

The runner tracks per-card and aggregate:

- **Token counts**: input, output, total (per step and cumulative)
- **Peak context**: maximum context window usage during session
- **Time spent**: wall-clock time per step and total (stored as milliseconds internally, displayed as seconds in output)
## Decisions

- **200K token context limit**: Agent manages own budget; comprehensive rules available for grepping but expensive to bulk-load. [SETTLED]
- **Rules as greppable file**: Comprehensive rules available in workspace as a file; agent greps for relevant sections. Best-practices doc provided in `rules_overview.md`. Replaces tool-based lookup for adapter fairness. [UPDATED]
- **Cost tracking enabled**: Token counts, peak context, and time tracked per card. [SETTLED]
- **foundations/ as browsable codebase**: Agent can list/read files, not expected to ingest everything. [SETTLED]
- **Standardized class names**: [template.py](http://template.py/) fixes class name and import path for cross-eval compatibility. [SETTLED]
- **Multi-agent via adapter pattern**: Pluggable `AgentAdapter` base class; v1 supports OpenCode, Claude Code, Aider, Pi. Config selects adapter. [SETTLED]
- **Per-round postmortem logging**: `postmortem.jsonl` captures agent output, file diffs, test results, and reasoning traces per round. `agent_thoughts.md` extracted for human review. [SETTLED]
- **Agent setup questioning**: Agents emit `setup_questions.json` to flag missing files, engine gaps, or ambiguous specs instead of silently failing. [SETTLED]
