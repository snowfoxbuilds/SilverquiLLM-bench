"""Benchmark CLI entry point.

Provides ``benchmark run``, ``benchmark eval``, ``benchmark score``,
and ``benchmark cards`` subcommands via Click.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from benchmark.card_loader import filter_by_collectors, filter_by_prototype, load_card_specs
from benchmark.config import load_config


# Resolve data paths relative to this file's location
_BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"


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

    # Print summary
    click.echo(f"Config loaded: {cfg.name}")
    click.echo(f"Cards: {len(specs)}")
    for spec in specs:
        name = spec.get("name", "???")
        tier = spec.get("tier", "unknown")
        click.echo(f"  [{tier}] {name}")

    if dry_run:
        click.echo(f"Dry run complete. {len(specs)} cards selected.")
        return


@main.command()
@click.option("--results-dir", required=True, help="Path to results directory.")
def eval(results_dir: str) -> None:
    """Run evaluation (not yet implemented)."""
    click.echo("Error: 'eval' is not yet implemented.", err=True)
    raise SystemExit(1)


@main.command()
@click.option("--results-dir", required=True, help="Path to results directory.")
def score(results_dir: str) -> None:
    """Compute scores (not yet implemented)."""
    click.echo("Error: 'score' is not yet implemented.", err=True)
    raise SystemExit(1)


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
        tier = card.get("tier", "unknown")
        click.echo(f"  [{tier}] {name}")


if __name__ == "__main__":
    main()
