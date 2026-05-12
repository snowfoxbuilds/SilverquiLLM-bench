"""Benchmark CLI entry point.

Provides ``benchmark run``, ``benchmark eval``, ``benchmark score``,
and ``benchmark cards`` subcommands via Click.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path

import click

from silverquillm.agent_session import (
    AgentSession,
    BlindResult,
    TestInformedResult,
    _append_regression_check,
    commit_engine_changes,
    compute_engine_diff,
    init_run_engine,
    save_engine_final,
)
from silverquillm.card_loader import filter_by_collectors, filter_by_prototype, load_card_specs
from silverquillm.config import BenchmarkConfig, load_config
from silverquillm.aggregator import aggregate_run, save_run_summary_v2
from silverquillm.evaluator import run_self_eval_flat
from silverquillm.post_eval import run_post_eval
from silverquillm.preflight import PreflightError, preflight_check
from silverquillm.evaluator import EvalResultV2
from silverquillm.results import init_results_dir, save_aggregates, save_card_result, save_card_result_v2, save_run_summary
from silverquillm.scorer import compute_scores, generate_leaderboard
from silverquillm.regression import CompletedCard, run_regressions
from silverquillm.replay.cli import validate as validate_cmd
from silverquillm.run_utils import _session_results_to_dicts


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _sys(msg: str) -> str:
    """Format a system message (bold green)."""
    return f"{_BOLD}{_GREEN}{msg}{_RESET}"


def _err(msg: str) -> str:
    """Format an error message (bold red)."""
    return f"{_BOLD}{_RED}{msg}{_RESET}"


def _warn(msg: str) -> str:
    """Format a warning message (yellow)."""
    return f"{_YELLOW}{msg}{_RESET}"


# Resolve data paths relative to this file's location
_BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"

# Tier ordering for sequential processing (trivial → expert).
# Unknown tiers sort last (high sentinel value).
_TIER_ORDER: dict[str, int] = {
    "trivial": 0,
    "simple": 1,
    "medium": 2,
    "complex": 3,
    "expert": 4,
}
_UNKNOWN_TIER_SENTINEL = max(_TIER_ORDER.values()) + 1


def _sort_cards_by_tier(specs: list[dict]) -> list[dict]:
    """Sort card specs by complexity tier then collector number.

    Ensures the agent processes simpler cards first, building up engine
    capabilities gradually.  Within the same tier, cards are sorted by
    collector number ascending for determinism.  Unknown tiers are placed
    last.
    """

    def _sort_key(spec: dict) -> tuple[int, int | float, str]:
        tier = spec.get("complexity_tier", spec.get("tier", ""))
        tier_rank = _TIER_ORDER.get(tier, _UNKNOWN_TIER_SENTINEL)
        collector = spec.get("collector_number", spec.get("number", ""))
        collector_str = str(collector)
        try:
            collector_num: int | float = int(collector_str)
        except (ValueError, TypeError):
            collector_num = float("inf")
        return (tier_rank, collector_num, collector_str)

    return sorted(specs, key=_sort_key)


@click.group()
def main() -> None:
    """SilverquiLLM benchmark runner."""


# Register the validate subcommand from silverquillm.replay.cli
main.add_command(validate_cmd)


@main.command()
@click.option("--config", "config_path", required=True, help="Path to YAML config file.")
@click.option("--cards", "card_ids", default=None, help="Comma-separated collector numbers to run.")
@click.option("--prototype", "use_prototype", is_flag=True, default=False, help="Use prototype card selection.")
@click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Print selected cards and exit.")
def run(config_path: str, card_ids: str | None, use_prototype: bool, dry_run: bool) -> None:
    """Run benchmark against selected cards."""
    if card_ids and use_prototype:
        raise click.UsageError("--cards and --prototype are mutually exclusive.")

    cfg = load_config(config_path)

    # Determine card_specs_dir: use config value or default convention
    specs_dir = cfg.card_specs_dir
    if not specs_dir:
        specs_dir = str(_BENCHMARKS_DIR / cfg.set_code.lower() / "cards")

    try:
        specs = load_card_specs(specs_dir)
    except FileNotFoundError:
        raise click.ClickException(f"Card specs directory not found: {specs_dir}")

    if not specs:
        click.echo(_err(f"No card specs found in {specs_dir}"), err=True)
        raise SystemExit(1)

    # Apply filters
    if card_ids:
        collector_numbers = [c.strip() for c in card_ids.split(",")]
        try:
            specs = filter_by_collectors(specs, collector_numbers)
        except ValueError as exc:
            raise click.UsageError(str(exc))
    elif use_prototype:
        prototype_path = str(_BENCHMARKS_DIR / cfg.set_code.lower() / "prototype_cards.json")
        try:
            specs = filter_by_prototype(specs, prototype_path)
        except (ValueError, FileNotFoundError) as exc:
            raise click.ClickException(f"Prototype filter error: {exc}")

    # Sort cards by complexity tier (trivial → expert), then collector number
    specs = _sort_cards_by_tier(specs)

    # Print summary
    click.echo(_sys(f"Config loaded: {cfg.name}"))
    click.echo(_sys(f"Cards: {len(specs)}"))
    for spec in specs:
        name = spec.get("name", "???")
        tier = spec.get("complexity_tier", spec.get("tier", "unknown"))
        click.echo(_sys(f"  [{tier}] {name}"))

    if dry_run:
        # Use MockAdapter for quick environment validation
        from silverquillm.adapters.mock import MockAdapter
        click.echo(_sys("Dry run: using MockAdapter for environment validation"))
        mock_adapter = MockAdapter(cfg, behavior="write")
        mock_adapter.setup()
        mock_adapter.teardown()
        click.echo(_sys(f"Dry run complete. {len(specs)} cards selected. MockAdapter OK."))
        return

    # --- Orchestration loop ---
    run_dir = init_results_dir(cfg)

    # Pre-flight validation before any LLM calls
    try:
        from silverquillm.preflight import preflight_check, PreflightError
        preflight_check(cfg, Path(run_dir))
    except PreflightError as exc:
        raise click.ClickException(str(exc))

    total = len(specs)
    failures: list[tuple[str, Exception]] = []
    completed_cards: list[CompletedCard] = []
    start_time = time.time()

    # Persistent engine: initialise run-level engine directory
    run_engine_dir = init_run_engine(run_dir)

    # Clean up any stale .workspace/ from a previous aborted run
    stale_workspace = Path(__file__).resolve().parent.parent / ".workspace"
    if stale_workspace.exists():
        click.echo(_warn(f"Cleaning up stale workspace from previous run: {stale_workspace}"))
        for root, dirs, files in os.walk(stale_workspace):
            for dname in dirs:
                try:
                    (Path(root) / dname).chmod(0o755)
                except OSError:
                    pass
            for fname in files:
                try:
                    (Path(root) / fname).chmod(0o644)
                except OSError:
                    pass
        shutil.rmtree(stale_workspace, ignore_errors=True)

    for i, spec in enumerate(specs, 1):
        card_name = spec.get("name", "???")
        card_dir_name = spec.get("card_dir_name", spec.get("collector_number", spec.get("number", "unknown")))
        collector_number = spec.get("collector_number", spec.get("number", "unknown"))
        card_dir = f"{specs_dir}/{card_dir_name}/"

        session: AgentSession | None = None
        try:
            session = AgentSession(
                config=cfg, card_spec=spec, card_dir=card_dir,
                run_engine_dir=run_engine_dir,
                run_dir=run_dir,
            )
            workspace = session.setup_workspace()

            card_run_result = session.run_card()

            # Build legacy result dicts for backward compatibility
            from silverquillm.strategies import CardRunStatus
            run_status = card_run_result.status.value
            impl_path = workspace / "card_impl.py" if (workspace / "card_impl.py").exists() else None
            runtime_s = card_run_result.runtime_ms / 1000 if card_run_result.runtime_ms else 0

            if cfg.mode == "impl_test":
                # In impl_test mode, record as a tested result
                blind_result = BlindResult(
                    impl_path=None,
                    tokens=0,
                    runtime_seconds=0,
                    peak_context=0,
                    status="skipped",
                )
                tests_path_ws = workspace / "tests.py"
                tested_result = TestInformedResult(
                    impl_path=impl_path,
                    tests_path=tests_path_ws if tests_path_ws.exists() else None,
                    iterations=1,
                    tokens=0,
                    runtime_seconds=runtime_s,
                    peak_context=0,
                    status=run_status,
                )
            else:
                blind_result = BlindResult(
                    impl_path=impl_path,
                    tokens=0,
                    runtime_seconds=runtime_s,
                    peak_context=0,
                    status=run_status,
                )
                tested_result = None

            # Read source files before cleanup destroys the workspace
            blind_dict, test_dict = _session_results_to_dicts(
                blind_result, tested_result, spec, cfg
            )

            # Propagate violations into result dicts so result.json is annotated
            if card_run_result.violations:
                blind_dict["violations"] = list(card_run_result.violations)

            card_results_dir = run_dir / "cards" / str(card_dir_name)
            save_card_result(run_dir, card_dir_name, blind_dict, test_dict)

            # Overwrite result.json with v2 schema
            _active = test_dict if cfg.mode == "impl_test" else blind_dict
            _v2_result = EvalResultV2(
                card_id=str(card_dir_name),
                mode=cfg.mode,
                model_name=_active.get("model", cfg.model_name),
                adapter=_active.get("agent", getattr(cfg.agent, "adapter", "unknown")),
                status=_active.get("status", "completed"),
                complexity_tier=_active.get("complexity_tier", _active.get("tier", "unknown")),
                implementation={
                    "tokens": _active.get("tokens", 0),
                    "runtime_ms": int(_active.get("runtime_seconds", 0) * 1000),
                    "peak_context": _active.get("peak_context", 0),
                },
                errors=[],
            )
            save_card_result_v2(
                run_dir, _v2_result,
                impl_source=_active.get("impl_source", ""),
                tests_source=_active.get("tests_source", ""),
            )

            # Copy raw implementation files from workspace to results dir
            session.harvest_results(card_results_dir)

            # Capture engine diff before committing changes
            compute_engine_diff(workspace, run_engine_dir, card_results_dir)

            # Commit engine changes back to run-level directory
            commit_engine_changes(workspace, run_engine_dir)

            # Run regressions against all previously-completed cards
            if completed_cards:
                regression_result = run_regressions(
                    completed_cards,
                    run_engine_dir=run_engine_dir,
                )
                # Emit structured regression_check event
                pm_path = run_dir / "cards" / card_name / "postmortem.jsonl"
                _append_regression_check(
                    pm_path,
                    status="fail" if regression_result.has_failures else "pass",
                    cards_failed=regression_result.cards_failed,
                    total_cards=regression_result.total_cards,
                )
                if regression_result.has_failures:
                    click.echo(
                        _warn(
                            f"[{i}/{total}] {card_name}: "
                            f"regressions={regression_result.cards_failed}/{regression_result.total_cards} failed"
                        ),
                        err=True,
                    )

            # Record this card as completed for future regression runs
            tests_path = card_results_dir / "tests.py"
            impl_path = card_results_dir / "card_impl.py"
            if tests_path.exists():
                completed_cards.append(CompletedCard(
                    card_id=str(card_dir_name),
                    workspace=card_results_dir,
                    tests_file=tests_path,
                    impl_file=impl_path if impl_path.exists() else None,
                ))
            blind_status_str = blind_result.status
            tested_status_str = tested_result.status if tested_result else "skipped"
            click.echo(
                _sys(f"[{i}/{total}] {card_name}: blind={blind_status_str}, tested={tested_status_str}")
            )
        except Exception as exc:  # noqa: BLE001
            failures.append((card_name, exc))
            click.echo(
                _err(f"[{i}/{total}] {card_name}: error={exc!r}"), err=True
            )
        finally:
            if session is not None:
                session.cleanup()

    # Save final engine state as a run artifact
    save_engine_final(run_engine_dir, run_dir)

    # --- Post-loop: evaluation phase (all tests against final engine state) ---
    elapsed = time.time() - start_time
    cards_dir = run_dir / "cards"
    all_results: list[dict] = []

    # Run post-eval: evaluates all cards against the final engine state
    post_eval_results = run_post_eval(run_dir, mode=cfg.mode)

    # Build all_results from the updated result.json files
    if cards_dir.exists():
        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            result_json = card_path / "result.json"
            if not result_json.exists():
                continue
            record = json.loads(result_json.read_text())
            all_results.append(record)

    save_run_summary(run_dir, all_results)

    # --- Aggregate run_summary.json ---
    run_summary = aggregate_run(run_dir)
    save_run_summary_v2(run_dir, run_summary)

    # --- Print summary ---
    blind_passed = sum((r.get("self_eval") or {}).get("blind", {}).get("passed", 0) for r in all_results)
    blind_total_tests = sum((r.get("self_eval") or {}).get("blind", {}).get("total", 0) for r in all_results)
    tested_passed = sum((r.get("self_eval") or {}).get("tested", {}).get("passed", 0) for r in all_results)
    tested_total_tests = sum((r.get("self_eval") or {}).get("tested", {}).get("total", 0) for r in all_results)

    click.echo(_sys(f"\n--- Run Summary ---"))
    click.echo(_sys(f"Cards run: {len(all_results)}"))
    if blind_total_tests > 0:
        blind_rate = blind_passed / blind_total_tests * 100
        click.echo(_sys(f"Self-eval blind pass rate: {blind_passed}/{blind_total_tests} ({blind_rate:.1f}%)"))
    else:
        click.echo(_sys(f"Self-eval blind pass rate: 0/0 (N/A)"))
    if tested_total_tests > 0:
        tested_rate = tested_passed / tested_total_tests * 100
        click.echo(_sys(f"Self-eval tested pass rate: {tested_passed}/{tested_total_tests} ({tested_rate:.1f}%)"))
    else:
        click.echo(_sys(f"Self-eval tested pass rate: 0/0 (N/A)"))
    click.echo(_sys(f"Elapsed time: {elapsed:.1f}s"))

    if failures:
        click.echo(_err(f"\n{len(failures)} card(s) failed:"), err=True)
        for name, exc in failures:
            click.echo(_err(f"  {name}: {exc!r}"), err=True)
        raise SystemExit(1)


@main.command("eval")
@click.option("--results-dir", required=True, help="Path to results directory.")
@click.option("--audited-tests", default=None, type=click.Path(exists=True), help="Path to gold-standard test file.")
@click.option("--audited-dir", default=None, type=click.Path(exists=True), help="Path to per-card audited test directory.")
def eval_cmd(results_dir: str, audited_tests: str | None, audited_dir: str | None) -> None:
    """Run evaluation on existing results."""
    import yaml

    from silverquillm.evaluator import EvalResult, run_audited_eval_per_card, run_self_eval_flat, run_tests

    results_path = Path(results_dir)
    if not results_path.exists():
        raise click.ClickException(f"Results directory not found: {results_dir}")

    # Step 1: Scan results_dir to find run directories (each has config.yaml + cards/)
    run_dirs: list[Path] = []
    # Check if results_dir itself is a run directory
    if (results_path / "config.yaml").exists() and (results_path / "cards").exists():
        run_dirs.append(results_path)
    else:
        # Look for subdirectories that are run directories
        for sub in sorted(results_path.iterdir()):
            if sub.is_dir() and (sub / "config.yaml").exists() and (sub / "cards").exists():
                run_dirs.append(sub)

    if not run_dirs:
        raise click.ClickException(f"No run directories found in {results_dir}")

    all_eval_results: list[dict] = []
    total_cards = 0

    for run_dir in run_dirs:
        # Step 2: Detect agents from config.yaml
        config_file = run_dir / "config.yaml"
        with open(config_file) as f:
            run_config = yaml.safe_load(f)
        agent_name = run_config.get("model_name", "unknown")

        cards_dir = run_dir / "cards"
        if not cards_dir.exists():
            continue

        agents = [agent_name]
        num_agents = len(agents)

        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            total_cards += 1

            # Step 3: Single-agent runs — run self-eval flat
            if num_agents == 1:
                eval_result = run_self_eval_flat(card_path, agent_name)
                all_eval_results.append(asdict(eval_result))
            else:
                # Step 4: Multi-agent cross-eval (future)
                # TODO: multi-agent cross-eval consolidation
                pass

            # Step 5: If --audited-tests provided, run audited eval
            if audited_tests:
                audited_path = Path(audited_tests)
                blind_impl = card_path / "blind_impl.py"
                tested_impl = card_path / "tested_impl.py"

                all_errors: list[str] = []
                bp, bf, bt = 0, 0, 0
                tp, tf, tt = 0, 0, 0

                if blind_impl.exists() and audited_path.exists():
                    bp, bf, bt, be = run_tests(blind_impl, audited_path)
                    all_errors.extend(be)

                if tested_impl.exists() and audited_path.exists():
                    tp, tf, tt, te = run_tests(tested_impl, audited_path)
                    all_errors.extend(te)

                audited_result = EvalResult(
                    card_id=card_path.name,
                    agent=agent_name,
                    eval_type="audited",
                    blind_passed=bp,
                    blind_failed=bf,
                    blind_total=bt,
                    tested_passed=tp,
                    tested_failed=tf,
                    tested_total=tt,
                    errors=all_errors,
                )
                all_eval_results.append(asdict(audited_result))

            # Step 5b: If --audited-dir provided, run per-card audited eval
            if audited_dir:
                audited_dir_path = Path(audited_dir)
                card_id = card_path.name
                blind_impl = card_path / "blind_impl.py"
                tested_impl = card_path / "tested_impl.py"

                all_errors_pc: list[str] = []

                # Always call run_audited_eval_per_card so missing impls
                # are reported as audited errors (not silently skipped).
                bp, bf, bt, be = run_audited_eval_per_card(
                    blind_impl, card_id, audited_dir_path
                )
                all_errors_pc.extend(be)

                tp, tf, tt, te = run_audited_eval_per_card(
                    tested_impl, card_id, audited_dir_path
                )
                all_errors_pc.extend(te)

                audited_result = EvalResult(
                    card_id=card_id,
                    agent=agent_name,
                    eval_type="audited",
                    blind_passed=bp,
                    blind_failed=bf,
                    blind_total=bt,
                    tested_passed=tp,
                    tested_failed=tf,
                    tested_total=tt,
                    errors=all_errors_pc,
                )
                all_eval_results.append(asdict(audited_result))

                # Also record in per-card result.json under audited_eval
                card_result_json = card_path / "result.json"
                if card_result_json.exists():
                    card_record = json.loads(card_result_json.read_text())
                else:
                    card_record = {}
                card_record["audited_eval"] = {
                    "blind": {
                        "passed": bp,
                        "failed": bf,
                        "total": bt,
                        "errors": be,
                    },
                    "tested": {
                        "passed": tp,
                        "failed": tf,
                        "total": tt,
                        "errors": te,
                    },
                    "errors": all_errors_pc,
                }
                card_result_json.write_text(
                    json.dumps(card_record, indent=2, default=str)
                )

    # Step 6: Deduplicate by (agent, card_id, eval_type), keeping the last entry
    # (latest run wins since run_dirs are sorted by name/timestamp).
    deduped: dict[tuple[str, str, str], dict] = {}
    for r in all_eval_results:
        key = (r.get("agent", ""), r.get("card_id", ""), r.get("eval_type", ""))
        deduped[key] = r
    all_eval_results = list(deduped.values())

    # Save all eval results as JSON list in results_dir/results.json
    output_file = results_path / "results.json"
    output_file.write_text(json.dumps(all_eval_results, indent=2, default=str))

    # Step 7: Print eval summary
    click.echo(_sys(f"\n--- Eval Summary ---"))
    click.echo(_sys(f"Cards evaluated: {total_cards}"))

    # Pass rates by eval type
    by_type: dict[str, list[dict]] = {}
    for r in all_eval_results:
        et = r.get("eval_type", "unknown")
        by_type.setdefault(et, []).append(r)

    for eval_type, results in sorted(by_type.items()):
        blind_passed = sum(r.get("blind_passed", 0) for r in results)
        blind_total = sum(r.get("blind_total", 0) for r in results)
        tested_passed = sum(r.get("tested_passed", 0) for r in results)
        tested_total = sum(r.get("tested_total", 0) for r in results)

        if blind_total > 0:
            blind_rate = blind_passed / blind_total * 100
            click.echo(_sys(f"  [{eval_type}] blind: {blind_passed}/{blind_total} ({blind_rate:.1f}%)"))
        else:
            click.echo(_sys(f"  [{eval_type}] blind: 0/0 (N/A)"))

        if tested_total > 0:
            tested_rate = tested_passed / tested_total * 100
            click.echo(_sys(f"  [{eval_type}] tested: {tested_passed}/{tested_total} ({tested_rate:.1f}%)"))
        else:
            click.echo(_sys(f"  [{eval_type}] tested: 0/0 (N/A)"))

    click.echo(_sys(f"Results saved to: {output_file}"))


@main.command()
@click.option("--results-dir", required=True, help="Path to results directory.")
@click.option(
    "--tier-data",
    default=None,
    type=click.Path(exists=False),
    help="Path to tier data JSON. Defaults to benchmarks/{set}/data/{set}_classified.json.",
)
@click.option("--set", "set_code", default="sos", help="Set code for default tier data path resolution.")
def score(results_dir: str, tier_data: str | None, set_code: str) -> None:
    """Compute scores and generate leaderboard."""
    results_path = Path(results_dir)

    # Load tier data
    set_code = set_code.lower()
    if tier_data is None:
        tier_data_path = _BENCHMARKS_DIR / set_code / "data" / f"{set_code}_classified.json"
    else:
        tier_data_path = Path(tier_data)

    with open(tier_data_path) as f:
        classified = json.load(f)

    # Build collector_number → tier mapping
    tier_map: dict[str, str] = {
        entry["collector_number"]: entry.get("complexity_tier", entry.get("tier", "unknown"))
        for entry in classified
    }

    # Compute scores
    scores = compute_scores(results_path, tier_map)

    # Generate and print leaderboard
    leaderboard_md = generate_leaderboard(scores)
    click.echo(leaderboard_md)

    # Collect run directories
    run_dirs = [d for d in results_path.iterdir() if d.is_dir()]

    # Save aggregates
    save_aggregates(results_path, run_dirs, scores)

    # Print paths to written files
    click.echo(_sys(f"Written: {results_path / 'leaderboard.md'}"))
    click.echo(_sys(f"Written: {results_path / 'summary.json'}"))


@main.command()
@click.option("--set", "set_code", required=True, help="Benchmark set code (e.g. SOS).")
def cards(set_code: str) -> None:
    """List cards with tiers from classified data."""
    data_file = _BENCHMARKS_DIR / set_code.lower() / "data" / f"{set_code.lower()}_classified.json"

    if not data_file.exists():
        click.echo(_err(f"No classified data found for set '{set_code}' at {data_file}"), err=True)
        raise SystemExit(1)

    with open(data_file) as f:
        card_list = json.load(f)

    click.echo(_sys(f"Cards in set {set_code}: {len(card_list)}"))
    for card in card_list:
        name = card.get("name", "???")
        tier = card.get("complexity_tier", card.get("tier", "unknown"))
        click.echo(_sys(f"  [{tier}] {name}"))


@main.command()
@click.argument("run_dir", type=click.Path(exists=True))
def aggregate(run_dir: str) -> None:
    """Aggregate per-card results into run_summary.json.

    Reads all cards/*/result.json in the given run directory and produces
    a run_summary.json.  Can be used to manually re-aggregate after editing
    individual card results.
    """
    run_path = Path(run_dir)
    summary = aggregate_run(run_path)
    out = save_run_summary_v2(run_path, summary)
    click.echo(_sys(f"Wrote {out}"))
    click.echo(_sys(f"  Total cards: {summary.total_cards}"))
    click.echo(_sys(f"  Completed: {summary.cards_completed}"))
    click.echo(_sys(f"  Timeout: {summary.cards_timeout}"))
    click.echo(_sys(f"  No output: {summary.cards_no_output}"))


if __name__ == "__main__":
    main()
