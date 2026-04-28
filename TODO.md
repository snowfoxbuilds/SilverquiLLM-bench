Phase 2: Benchmark Harness & Prototype

Scope: Fix Phase 1 bugs → build benchmark runner harness → validate with ~5 real Strixhaven (SOS) cards. Strixhaven released 2026-04-24. Phase 1 items archived to TODO_COMPLETED.

---

- [x] **Fix Phase 1 tech debt**
  Detail: Three non-blocking issues from PR review that should be cleaned up before new code is added.

  1. **Python version alignment**: `pyproject.toml` says `requires-python = ">=3.10"` but `ruff.toml` targets `py311`. Set both to Python 3.12: change `pyproject.toml` to `requires-python = ">=3.12"` and `ruff.toml` to `target-version = "py312"`. Update KEY_DECISION #2 accordingly.
  2. **Remove backward-compat aliases**: In `cards/foundations/simple_spells.py`, aliases like `LightningBolt = BurstLightning` map non-FDN card names to FDN cards with different stats (e.g., Lightning Bolt does 3 damage but Burst Lightning does 2). Remove all such aliases. Update any test imports that reference removed aliases to use the correct FDN card name.
  3. **Cleanup discard fallback warning**: In `engine/turn.py`, the cleanup step catches `ScriptExhaustedError` and silently discards `hand[-1]` (KEY_DECISION #21). Add `import warnings` and emit `warnings.warn(f"ScriptExhaustedError during cleanup discard for {player.name}; auto-discarding {card.name}")` so test authors know their script was incomplete.
  - Testability: `ruff check .` passes after version change. Removed aliases cause `ImportError` if any test still references them (fix those tests). Warning is captured by `pytest -W error::UserWarning` in a dedicated test.
- [ ] **Benchmark package scaffold + SOS data fetch**
  Detail: Create the `benchmark/` runner package and the `benchmarks/sos/` set directory, then fetch Secrets of Strixhaven card data.

  - Create `benchmark/` package (set-agnostic runner code) with `__init__.py`.
  - Create `benchmarks/sos/` directory with `data/`, `cards/`, `results/` subdirs. All SOS-specific artifacts live here so future sets get their own `benchmarks/{set_code}/` directory.
  - Add `pyyaml` and `click` to `pyproject.toml` dependencies (runner needs YAML config and CLI framework).
  - Extend the existing `cards/scryfall.py` `fetch_set()` function to fetch set code `"sos"`. Cache result to `benchmarks/sos/data/sos.json`. If `fetch_set` already works generically (it should — it takes a set_code parameter), just run it and commit the cached data.
  - Log stats after fetch: total card count, breakdown by card type (creature, instant, sorcery, enchantment, artifact, planeswalker, land), rarity distribution, and list of cards using new mechanics (search oracle text for "Prepared", "Converge", "Miracle", "Opus").
  - Testability: `benchmarks/sos/data/sos.json` exists, is valid JSON, every card has `name`, `mana_cost_str`, `type_line`, `oracle_text` fields. `import benchmark` succeeds.
- [ ] **Card complexity classifier**
  Detail: Classify each SOS card into a complexity tier for weighted scoring.

  - File: `benchmark/card_classifier.py`
  - Function: `classify_card(card: CardMetadata) -> str` returning one of `"trivial"`, `"simple"`, `"medium"`, `"complex"`, `"expert"`.
  - Function: `classify_set(cards: list[CardMetadata]) -> dict[str, list[CardMetadata]]` grouping cards by tier.
  - Heuristics (per [SCORING.md](http://scoring.md/)):
    - **Trivial (1x)**: No rules text or just keyword abilities, vanilla creatures, basic lands
    - **Simple (2x)**: Single keyword or one straightforward ability (e.g., ETB draw a card)
    - **Medium (3x)**: Multiple abilities, targeting, or conditional effects
    - **Complex (4x)**: Multi-step abilities, replacement effects, modal spells, new mechanics (Prepared, Converge, Opus)
    - **Expert (5x)**: Planeswalkers, complex state machines, unusual mechanics, Miracle
  - Concrete signals: `len(oracle_text)`, count of `\n` in oracle text (proxy for ability count), presence of "target" keyword, presence of new SOS mechanic keywords, card type (planeswalker → Expert floor), keyword count.
  - Output: `classify_set` writes `benchmarks/sos/data/sos_classified.json` — array of `{"name": ..., "collector_number": ..., "tier": ..., "weight": ...}`.
  - Testability: every SOS card gets a tier. Distribution is non-degenerate (no single tier has >60% of cards). A known vanilla creature classifies as "trivial". A known planeswalker classifies as "expert".
- [ ] **Card spec generator**
  Detail: Generate per-card JSON spec files that agents receive as context.

  - File: `benchmark/card_spec.py`
  - Function: `generate_card_spec(card: CardMetadata, tier: str) -> dict` returns spec dict.
  - Function: `generate_all_specs(set_code: str, output_dir: str)` generates one `card_spec.json` per card.
  - Output path: `benchmarks/sos/cards/{collector_number}/card_spec.json`
  - Schema:
```json
{
	"name": "Strixhaven Prodigy",
	"mana_cost": "{1}{U}",
	"type_line": "Creature — Human Wizard",
	"oracle_text": "When Strixhaven Prodigy enters...",
	"power": "2",
	"toughness": "1",
	"loyalty": null,
	"colors": ["U"],
	"keywords": [],
	"rarity": "uncommon",
	"set_code": "sos",
	"collector_number": "042",
	"complexity_tier": "medium"
}
```

- Source data from `benchmarks/sos/data/sos.json` (Scryfall cache) + `benchmarks/sos/data/sos_classified.json` (classifier output).
- Testability: generate specs for all SOS cards, verify every field is non-null (except loyalty for non-planeswalkers and power/toughness for non-creatures). JSON is valid and parseable.
- [ ] **Template generator**
  Detail: Generate the Python skeleton file each agent starts from, per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) cross-eval spec.

  - File: `benchmark/template_gen.py`
  - Function: `generate_template(card_spec: dict) -> str` returns Python source string.
  - Function: `card_name_to_class_name(name: str) -> str` converts "Strixhaven Prodigy" → "StrixhavenProdigy" (strip non-alphanumeric, PascalCase).
  - Template output must include:
    - `from engine.card import *` and `from engine.types import *` imports
    - Class name from `card_name_to_class_name(spec["name"])`
    - Correct base class: map `type_line` to base class — "Creature" → `Creature`, "Instant" → `Instant`, "Sorcery" → `Sorcery`, "Enchantment" → `Enchantment`, "Artifact" → `Artifact`, "Planeswalker" → `Planeswalker`, "Land" → `Land`. "Artifact Creature" → `ArtifactCreature`. "Enchantment Creature" → `Creature` (with enchantment types added). Default to `CardImpl` if ambiguous.
    - Docstring with card name
    - Stub `name`, `mana_cost`, `card_types`, `rules_text` attributes from spec
    - Stub `power`/`toughness` for creatures, `starting_loyalty` for planeswalkers
  - Per KEY_DECISION #6: subclass constructors union mandatory CardType. Template should follow the same pattern (e.g., `card_types = [CardType.CREATURE]` not empty).
  - Testability: generate template for a creature, instant, and planeswalker spec. Each template `exec()`s without error. Class name matches expected PascalCase. Base class is correct.
- [ ] **Engine API docs auto-generation**
  Detail: Generate `engine_api.md` from engine source code for agent consumption.

  - File: `benchmark/docs_gen.py`
  - Function: `generate_engine_api_doc(engine_dir: str = "engine") -> str` returns Markdown.
  - Use `ast` module to parse each `.py` file in `engine/`. Extract:
    - Class names + docstrings + method signatures (public methods only, skip `_private`)
    - Enum members (Color, ManaType, Zone, Phase, Step, CardType, Keyword, etc.)
    - Top-level function signatures (cast_spell, play_land, activate_ability, etc.)
    - Dataclass fields (ActivatedAbility, TargetRequirement, ContinuousEffect, Mode, etc.)
  - Group by module. Include brief examples for key operations (cast_spell, register_trigger, add continuous effect).
  - Target: **under 5,000 tokens**. Count tokens using `len(text.split()) * 1.3` as approximation. If over budget, trim docstrings and omit private helper classes.
  - Write output to `docs/engine_api.md`.
  - Testability: generated doc mentions all public engine classes (GameState, CardImpl, Creature, Stack, etc.). Token count < 5,000. Markdown renders without errors.
- [ ] **test_utils documentation for agents**
  Detail: Generate `test_utils.md` describing the test helper API that benchmark agents must use.

  - File: `benchmark/test_utils_doc.py` (or hand-write `docs/test_utils.md`)
  - Document each public function from `tests/test_utils.py`: `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`.
  - For each function: signature, description, parameter types, example usage snippet.
  - Include the required test structure:
```python
import pytest
from tests.test_utils import create_game, set_board_state, cast_spell

class TestCardName:
	def test_basic_cast(self):
		game = create_game()
		set_board_state(game, 0, hand=["CardName"], mana="{2}{W}")
		cast_spell(game, 0, "CardName")
		assert ...
```

- Include constraints: max 30 tests per card, must use helpers, import from `card_impl`.
- Target: **under 2,000 tokens**.
- Write output to `docs/test_utils.md`.
- Testability: all test_utils public functions appear in the doc. Example code is syntactically valid Python.
- [ ] **MTG rules indexer + rules_**[**overview.md**](http://overview.md/)
  Detail: Build a searchable index of MTG comprehensive rules and a compact overview document.

  - File: `benchmark/rules_skill.py`
  - Function: `download_comprehensive_rules() -> str` fetches the current MTG comprehensive rules text from `media.wizards.com/images/magic/comprules/MagicCompRules.txt` (or similar URL). Cache to `benchmarks/sos/data/comprehensive_rules.txt` (rules change per expansion, so they're pinned per benchmark set).
  - Function: `build_rules_index(rules_text: str) -> dict[str, list[str]]` parses rules into sections by rule number (e.g., "702.9" → flying rules text). Build keyword → rule numbers mapping.
  - Function: `lookup_rule(index: dict, query: str) -> str` returns relevant rule sections for a query (by number like "702.9" or keyword like "flying" or mechanic like "Prepared").
  - Generate `benchmarks/sos/data/rules_overview.md`: high-level summary of MTG rules (~1,000 tokens). Cover: turn structure, casting, stack, combat, zones, targeting, keywords, SBAs. This is always in agent context.
  - The `lookup_rule` function will be exposed as an OpenCode tool in the agent session manager (next items). For now, just build the indexer and verify it works standalone.
  - Testability: `lookup_rule(index, "flying")` returns text containing "702.9" or similar. `lookup_rule(index, "702.2")` returns the first strike rule. `benchmarks/sos/data/rules_overview.md` exists and is under 1,000 tokens.
- [ ] **Runner CLI scaffold + YAML config**
  Detail: Create the benchmark CLI entry point and configuration loading.

  - File: `benchmark/cli.py` — use `click` for CLI framework.
  - Entry point: add `[project.scripts] benchmark = "benchmark.cli:main"` to `pyproject.toml`.
  - Subcommands (stubs that load config and print status):
    - `benchmark run --config config.yaml` — will run benchmark (stub: load config, print card count)
    - `benchmark eval --results-dir ./results/` — will run evaluation (stub)
    - `benchmark score --results-dir ./results/` — will compute scores (stub)
    - `benchmark cards --set SOS` — list cards with tiers from `benchmarks/sos/data/sos_classified.json`
  - File: `benchmark/config.py`
  - Function: `load_config(path: str) -> BenchmarkConfig` loads and validates YAML.
  - Dataclass `BenchmarkConfig`:
```python
@dataclass
class BenchmarkConfig:
	name: str  # e.g. "magicbench-v1-strixhaven"
	set_code: str  # e.g. "SOS"
	model_name: str
	model_provider: str  # "anthropic", "openai", etc.
	max_context: int  # default 200000
	temperature: float  # default 0.0
	agent_tool: str  # "opencode"
	max_test_rounds: int  # default 3
	timeout_per_card: int  # default 300
	disable_web_search: bool  # default True
	card_specs_dir: str
	engine_docs_path: str
	template_dir: str
	output_dir: str
```

- Include a `config.example.yaml` in the repo root.
- Testability: `benchmark --help` prints usage. `benchmark cards --set SOS` lists cards with tiers. `load_config` raises `ValueError` on missing required fields.
- [ ] **Prompt templates module**
  Detail: Implement the parameterized prompt templates from [BENCHMARK-RUNNER.md](http://benchmark-runner.md/).

  - File: `benchmark/prompts.py`
  - Function: `blind_implementation_prompt(card_spec: dict) -> str` fills in card name, mana cost, type line, oracle text. Matches the Step 1 prompt from [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) exactly.
  - Function: `test_informed_prompt(card_spec: dict, round_num: int, prev_test_results: str | None = None) -> str` — Step 2 prompt. If `prev_test_results` is provided, includes test output feedback.
  - Function: `iteration_feedback_prompt(test_output: str, round_num: int, max_rounds: int) -> str` — feedback between iteration rounds, showing which tests passed/failed.
  - All prompts stored as template strings with `{placeholder}` substitution. No f-strings with complex logic.
  - Testability: generate prompts for a sample card_spec dict. Verify no `{placeholder}` remains in output. Verify blind prompt does NOT mention test_utils. Verify test-informed prompt DOES mention test_utils constraints (max 30, must use helpers, import from card_impl).
- [ ] **Agent session manager**
  Detail: Manage per-card agent sessions with contamination controls via OpenCode.

  - File: `benchmark/agent_session.py`
  - Class: `AgentSession`
    - Constructor: `__init__(self, config: BenchmarkConfig, card_spec: dict, card_dir: str)`
    - Method: `setup_workspace(self) -> Path` — create fresh temp directory, copy in:
      - `card_spec.json` (from card_dir)
      - `engine_api.md` (from docs/)
      - `base_classes.py` — extract CardImpl and subclass definitions from engine/[card.py](http://card.py/)
      - `template.py` (generated for this card)
      - `rules_overview.md` (from `benchmarks/sos/data/`)
      - `foundations/` directory (read-only copy of cards/foundations/)
    - Method: `configure_opencode(self, workspace: Path) -> dict` — return OpenCode config dict with permissions: deny web fetch, deny network, allow only workspace directory reads/writes.
    - Method: `run_blind_implementation(self, workspace: Path) -> BlindResult` — launch OpenCode with Step 1 prompt, collect output as `blind_impl.py`, record token counts and timing.
    - Method: `run_test_informed(self, workspace: Path, blind_impl: Path) -> TestInformedResult` — inject `test_utils.md`, launch Step 2 prompt, iterate up to `max_test_rounds` times (run pytest between rounds, feed results back), collect `tested_impl.py` + `tests.py`.
    - Method: `cleanup(self)` — remove temp directory.
  - Dataclasses: `BlindResult(impl_path, tokens, runtime_seconds, peak_context)`, `TestInformedResult(impl_path, tests_path, iterations, tokens, runtime_seconds, peak_context, rules_lookups)`.
  - Error handling per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/): timeout → record "timeout", syntax error → feed to correction round, no output → record "no_output", wrong files modified → discard + record "violation".
  - **Note**: actual OpenCode subprocess invocation depends on OpenCode's CLI/API interface. Implement the workspace setup and config generation concretely; the OpenCode invocation can use `subprocess.run` with the configured command. If OpenCode's exact CLI flags aren't known, implement a `_run_opencode(self, prompt, workspace) -> str` method with a clear interface that can be swapped.
  - Testability: `setup_workspace` creates temp dir with all expected files. `configure_opencode` returns dict with deny-web permission. Mock the OpenCode subprocess to test the full flow: setup → blind → test-informed → cleanup. Verify token recording populates correctly.
- [ ] **Evaluation runner**
  Detail: Run implementations against test suites for self-eval and cross-eval.

  - File: `benchmark/evaluator.py`
  - Dataclass: `EvalResult(card_id, agent, eval_type, blind_passed, blind_failed, blind_total, tested_passed, tested_failed, tested_total, errors: list[str])`.
  - Function: `run_tests(impl_path: Path, tests_path: Path, timeout: int = 60) -> tuple[int, int, int, list[str]]` — copy `impl_path` to `card_impl.py` in a temp dir alongside `tests_path`, run `pytest tests_path --tb=short -q` in subprocess, parse output for pass/fail counts. Return `(passed, failed, total, error_messages)`.
  - Function: `run_self_eval(card_dir: Path, agent_name: str) -> EvalResult` — run agent's `blind_impl.py` and `tested_impl.py` against agent's `tests.py`.
  - Function: `run_cross_eval(card_dir: Path, agents: list[str]) -> list[EvalResult]` — for each (impl_agent, test_agent) pair where impl_agent != test_agent, run impl against tests. Returns N×(N-1) results.
  - Function: `run_audited_eval(card_dir: Path, agents: list[str], audited_tests: Path) -> list[EvalResult]` — run all agents' impls against gold-standard tests.
  - Implementation swap mechanism: copy the target `impl.py` to a well-known path (`card_impl.py`) in the test execution directory. Tests import from `card_impl` (per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) cross-eval spec), so swapping the file swaps the implementation.
  - Subprocess isolation: each pytest run in its own subprocess with `timeout` seconds limit. Capture stdout+stderr. Parse pytest output for `X passed, Y failed` pattern.
  - Testability: create two mock implementations (one correct, one buggy) and a test file. Run cross-eval. Verify the correct impl passes more tests. Verify timeout handling.
- [ ] **Scoring calculator**
  Detail: Compute all metrics from [SCORING.md](http://scoring.md/) across three independent categories.

  - File: `benchmark/scorer.py`
  - Function: `compute_scores(results_dir: Path, tier_data: dict) -> Leaderboard`
  - Dataclass `Leaderboard` with per-agent scores for each category:
    - **Category 1 (Blind)**: `audited_pass_rate`, `card_pass_rate`, `cross_eval_pass_rate`, `weighted_score`
    - **Category 2 (Tested)**: same four + `improvement_delta` (Cat2 audited - Cat1 audited)
    - **Category 3 (Test Quality)**: `audit_survival_rate`, `discrimination_score`, `difficulty_calibration`, `coverage`
  - Weighted score formula (per [SCORING.md](http://scoring.md/)): `Σ(w_c × pass(c)) / Σ(w_c)` where `w_c` is tier weight (1-5) and `pass(c) = 1 if all audited tests pass, 0 otherwise`.
  - Discrimination score: variance in pass rates across agents' implementations for each test. High variance = good differentiation.
  - Difficulty calibration: fraction of tests passed by some but not all agents.
  - Function: `generate_leaderboard(scores: Leaderboard) -> str` returns Markdown tables matching [SCORING.md](http://scoring.md/) format.
  - Testability: create mock eval results for 3 agents × 5 cards. Verify `weighted_score` matches hand calculation. Verify `improvement_delta` = Cat2 - Cat1. Verify discrimination score is 0 when all agents have identical pass rates.
- [ ] **Result recording + output artifacts**
  Detail: Write all benchmark results to a per-run directory structure under `benchmarks/sos/results/` (per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/)). Each run gets its own folder so results from different models or re-runs never collide.

  - File: `benchmark/results.py`
  - Function: `generate_run_name(config: BenchmarkConfig) -> str` returns `{model_name}_{ISO-timestamp}` (e.g. `claude-sonnet-4_2026-04-28T18-30`). Allow override via config or CLI flag.
  - Function: `init_results_dir(config: BenchmarkConfig, run_name: str | None = None) -> Path` creates:
```javascript
benchmarks/sos/results/{run_name}/
├── config.yaml (copy of run config)
└── cards/
```

- Function: `save_card_result(run_dir, card_id, blind_result, test_result, eval_results)` writes:
```javascript
cards/{card_id}/
├── blind_impl.py
├── tested_impl.py
├── tests.py
├── iterations/ (iteration_1/, iteration_2/, ...)
└── result.json
```

- Function: `save_run_summary(run_dir, all_results)` writes `summary.json` inside the run directory (per-run stats only).
- Function: `save_aggregates(results_dir, run_dirs: list[Path], leaderboard)` writes cross-run aggregates to the **parent** `benchmarks/sos/results/` directory:
```javascript
benchmarks/sos/results/
├── leaderboard.md          # Combined leaderboard across all runs
├── cross_eval_matrix.json  # Cross-eval across runs (if multi-model)
└── summary.json            # Aggregate stats across all runs
```

- `result.json` (per card, inside each run) schema matches the result record from [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) (card_id, agent, complexity_tier, implementation metrics, self_eval, cross_eval, audited_eval).
- `cross_eval_matrix.json`: `{"card_id": {"impl_agent": {"test_agent": {"passed": N, "failed": M}}}}`. For single-model runs this is empty.
- Testability: call `init_results_dir` twice with different run names, verify separate directories. Call `save_card_result` with mock data, verify all files exist and JSON is valid. Call `save_aggregates`, verify `summary.json` has correct card count and `leaderboard.md` matches scorer output.
- [ ] **Prototype card selection + engine gap analysis**
  Detail: Select ~5 SOS cards for the prototype run and identify engine gaps.

  - File: `benchmark/prototype.py`
  - Function: `select_prototype_cards(classified_path: str, count_per_tier: int = 1) -> list[dict]` — pick one card from each of the 5 complexity tiers. Prefer cards whose oracle text exercises distinct mechanics:
    - Trivial: vanilla creature (no abilities)
    - Simple: single keyword ability
    - Medium: targeted spell or multi-ability creature
    - Complex: card with a new SOS mechanic (Prepared, Converge, or Opus)
    - Expert: planeswalker or card with Miracle
  - Function: `analyze_engine_gaps(cards: list[dict], engine_dir: str = "engine") -> list[str]` — for each card's oracle text, check if the required mechanics exist in the engine:
    - Search for "Prepared" → check if `Keyword.PREPARED` exists in `engine/types.py`
    - Search for "Converge" → check if mana color tracking exists in `engine/mana.py`
    - Search for "Miracle" → check if draw-event hooks exist in `engine/triggers.py` or `engine/casting.py`
    - Search for "Opus" → check if modal spell infrastructure exists (it does: `get_modes()` per KEY_DECISION implicit in Card Interface spec)
  - Write selections to `benchmarks/sos/prototype_cards.json` with rationale.
  - Write gap analysis to `benchmarks/sos/prototype_gaps.md`.
  - Testability: exactly 5 cards selected, one per tier. `prototype_gaps.md` lists specific missing engine features (or "none" if covered).
- [ ] **Minimal engine extensions for SOS prototype mechanics**
  Detail: Implement the minimum engine changes needed to support the 5 prototype cards. Scope depends on gap analysis from previous item.

  - Likely extensions (implement only what the prototype cards actually need):
    - **Prepared**: If it's a keyword ability, add `PREPARED` to `Keyword` enum in `engine/types.py`. Add handling in the relevant engine system (likely a casting-time or combat-time check). Per KEY_DECISION #6, ensure subclass constructors union the keyword.
    - **Converge**: If it cares about colors of mana spent, add `colors_spent: list[Color]` tracking to the casting pipeline in `engine/casting.py`. Store on the card instance similar to `chosen_targets` (KEY_DECISION #16).
    - **Miracle**: If it's an alternate casting cost from draw, add a draw-event hook. The trigger system (engine/[triggers.py](http://triggers.py/)) already has `DRAWS_CARD` event type. Add a check: if the drawn card has Miracle AND it's the first card drawn this turn, allow casting at Miracle cost. This may need a new method on CardImpl: `get_miracle_cost()` and a flag `is_first_draw_this_turn` on GameState.
    - **Opus**: Likely modal — existing `get_modes()` infrastructure should cover it. May need mode count > 2 or "choose N modes" logic.
  - Each extension gets unit tests in isolation.
  - Do NOT over-engineer: only implement what the 5 prototype cards require. Leave stubs with `# TODO` for unused branches.
  - Testability: for each new mechanic, a unit test exercises the mechanic in isolation. The 5 prototype cards can be instantiated and their key methods called without `NotImplementedError`.
---

**Manual validation steps** (not auto-implementable — performed by human after the above items):

- **Prototype dry run**: Run `benchmark run --config prototype_config.yaml` with the 5 selected SOS cards × 1 model. Verify: agent receives correct context, blind impl produces valid Python, test iteration runs, eval produces results, scoring generates leaderboard, context stays within 200K.
- **Prompt iteration**: Review prototype results. Tune prompts based on common failures (wrong base class, missing imports, misunderstood mechanics). Re-run and compare.
---

**Note:** After Phase 2 validates the pipeline, Phase 3 will: (1) port remaining Foundations cards as needed for reference quality, (2) catalog full SOS set engine requirements and extend engine, (3) run full benchmark across multiple LLMs.
