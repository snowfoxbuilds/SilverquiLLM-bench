"""Benchmark CLI entry point.

Provides ``benchmark run``, ``benchmark eval``, ``benchmark score``,
and ``benchmark cards`` subcommands via Click.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import click

from silverquillm.agent_session import (
    AgentSession,
    commit_engine_changes,
    init_run_engine,
    save_engine_final,
)
from silverquillm.card_loader import filter_by_collectors, filter_by_prototype, load_card_specs
from silverquillm.config import BenchmarkConfig, load_config
from silverquillm.evaluator import run_self_eval_flat
from silverquillm.results import init_results_dir, save_aggregates, save_card_result, save_run_summary
from silverquillm.scorer import compute_scores, generate_leaderboard
from silverquillm.run_utils import _session_results_to_dicts


# Resolve data paths relative to this file's location
_BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"

# Tier ordering for sequential processing (trivial → expert).
# Unknown tiers sort last (high sentinel value).
_TIER_ORDER: dict[str, int] = {
    "trivial": 0,
    "simple": 1,
    "moderate": 2,
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
        click.echo(f"No card specs found in {specs_dir}", err=True)
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
    click.echo(f"Config loaded: {cfg.name}")
    click.echo(f"Cards: {len(specs)}")
    for spec in specs:
        name = spec.get("name", "???")
        tier = spec.get("complexity_tier", spec.get("tier", "unknown"))
        click.echo(f"  [{tier}] {name}")

    if dry_run:
        click.echo(f"Dry run complete. {len(specs)} cards selected.")
        return

    # --- Orchestration loop ---
    run_dir = init_results_dir(cfg)
    total = len(specs)
    failures: list[tuple[str, Exception]] = []
    start_time = time.time()

    # Persistent engine: initialise run-level engine directory
    run_engine_dir = init_run_engine(run_dir)

    for i, spec in enumerate(specs, 1):
        card_name = spec.get("name", "???")
        collector_number = spec.get("collector_number", spec.get("number", "unknown"))
        card_dir = f"{specs_dir}/{collector_number}/"

        session: AgentSession | None = None
        try:
            session = AgentSession(
                config=cfg, card_spec=spec, card_dir=card_dir,
                run_engine_dir=run_engine_dir,
            )
            workspace = session.setup_workspace()

            blind_result = session.run_blind_implementation(workspace)

            tested_result = None
            if (
                blind_result.impl_path
                and blind_result.status in ("ok", "syntax_error")
            ):
                tested_result = session.run_test_informed(workspace, blind_result.impl_path)

            # Read source files before cleanup destroys the workspace
            blind_dict, test_dict = _session_results_to_dicts(
                blind_result, tested_result, spec, cfg
            )

            save_card_result(run_dir, collector_number, blind_dict, test_dict)

            # Commit engine changes back to run-level directory
            commit_engine_changes(workspace, run_engine_dir)

            blind_status = blind_result.status
            tested_status = tested_result.status if tested_result else "skipped"
            click.echo(
                f"[{i}/{total}] {card_name}: blind={blind_status}, tested={tested_status}"
            )
        except Exception as exc:  # noqa: BLE001
            failures.append((card_name, exc))
            click.echo(
                f"[{i}/{total}] {card_name}: error={exc!r}", err=True
            )
        finally:
            if session is not None:
                session.cleanup()

    # Save final engine state as a run artifact
    save_engine_final(run_engine_dir, run_dir)

    # --- Post-loop: self-eval and summary ---
    elapsed = time.time() - start_time
    cards_dir = run_dir / "cards"
    all_results: list[dict] = []

    if cards_dir.exists():
        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            result_json = card_path / "result.json"
            if not result_json.exists():
                continue

            # Run self-eval on the flat layout
            eval_result = run_self_eval_flat(card_path, cfg.model_name)

            # Load existing result, merge self-eval, re-save
            record = json.loads(result_json.read_text())
            record["self_eval"] = {
                "blind": {
                    "passed": eval_result.blind_passed,
                    "failed": eval_result.blind_failed,
                    "total": eval_result.blind_total,
                    "errors": [e for e in eval_result.errors],
                },
                "tested": {
                    "passed": eval_result.tested_passed,
                    "failed": eval_result.tested_failed,
                    "total": eval_result.tested_total,
                    "errors": [],
                },
                "errors": eval_result.errors,
            }
            result_json.write_text(json.dumps(record, indent=2, default=str))
            all_results.append(record)

    save_run_summary(run_dir, all_results)

    # --- Print summary ---
    blind_passed = sum(r.get("self_eval", {}).get("blind", {}).get("passed", 0) for r in all_results)
    blind_total_tests = sum(r.get("self_eval", {}).get("blind", {}).get("total", 0) for r in all_results)
    tested_passed = sum(r.get("self_eval", {}).get("tested", {}).get("passed", 0) for r in all_results)
    tested_total_tests = sum(r.get("self_eval", {}).get("tested", {}).get("total", 0) for r in all_results)

    click.echo(f"\n--- Run Summary ---")
    click.echo(f"Cards run: {len(all_results)}")
    if blind_total_tests > 0:
        blind_rate = blind_passed / blind_total_tests * 100
        click.echo(f"Self-eval blind pass rate: {blind_passed}/{blind_total_tests} ({blind_rate:.1f}%)")
    else:
        click.echo(f"Self-eval blind pass rate: 0/0 (N/A)")
    if tested_total_tests > 0:
        tested_rate = tested_passed / tested_total_tests * 100
        click.echo(f"Self-eval tested pass rate: {tested_passed}/{tested_total_tests} ({tested_rate:.1f}%)")
    else:
        click.echo(f"Self-eval tested pass rate: 0/0 (N/A)")
    click.echo(f"Elapsed time: {elapsed:.1f}s")

    if failures:
        click.echo(f"\n{len(failures)} card(s) failed:", err=True)
        for name, exc in failures:
            click.echo(f"  {name}: {exc!r}", err=True)
        raise SystemExit(1)


@main.command("eval")
@click.option("--results-dir", required=True, help="Path to results directory.")
@click.option("--audited-tests", default=None, type=click.Path(exists=True), help="Path to gold-standard test file.")
def eval_cmd(results_dir: str, audited_tests: str | None) -> None:
    """Run evaluation on existing results."""
    import yaml

    from silverquillm.evaluator import EvalResult, run_self_eval_flat, run_tests

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
    click.echo(f"\n--- Eval Summary ---")
    click.echo(f"Cards evaluated: {total_cards}")

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
            click.echo(f"  [{eval_type}] blind: {blind_passed}/{blind_total} ({blind_rate:.1f}%)")
        else:
            click.echo(f"  [{eval_type}] blind: 0/0 (N/A)")

        if tested_total > 0:
            tested_rate = tested_passed / tested_total * 100
            click.echo(f"  [{eval_type}] tested: {tested_passed}/{tested_total} ({tested_rate:.1f}%)")
        else:
            click.echo(f"  [{eval_type}] tested: 0/0 (N/A)")

    click.echo(f"Results saved to: {output_file}")


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
    click.echo(f"Written: {results_path / 'leaderboard.md'}")
    click.echo(f"Written: {results_path / 'summary.json'}")


@main.command()
@click.option("--set", "set_code", required=True, help="Benchmark set code (e.g. SOS).")
def cards(set_code: str) -> None:
    """List cards with tiers from classified data."""
    data_file = _BENCHMARKS_DIR / set_code.lower() / "data" / f"{set_code.lower()}_classified.json"

    if not data_file.exists():
        click.echo(f"No classified data found for set '{set_code}' at {data_file}", err=True)
        raise SystemExit(1)

    with open(data_file) as f:
        card_list = json.load(f)

    click.echo(f"Cards in set {set_code}: {len(card_list)}")
    for card in card_list:
        name = card.get("name", "???")
        tier = card.get("complexity_tier", card.get("tier", "unknown"))
        click.echo(f"  [{tier}] {name}")


if __name__ == "__main__":
    main()
