"""Benchmark CLI entry point.

Provides ``benchmark run``, ``benchmark eval``, ``benchmark score``,
and ``benchmark cards`` subcommands via Click.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from benchmark.config import load_config


# Resolve data paths relative to this file's location
_BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"


@click.group()
def main() -> None:
    """SilverquiLLM benchmark runner."""


@main.command()
@click.option("--config", "config_path", required=True, help="Path to YAML config file.")
def run(config_path: str) -> None:
    """Run benchmark (stub: load config, print card count)."""
    cfg = load_config(config_path)

    # Count cards from classified data
    data_file = _BENCHMARKS_DIR / cfg.set_code.lower() / "data" / f"{cfg.set_code.lower()}_classified.json"
    if not data_file.exists():
        click.echo(f"No classified data found for set '{cfg.set_code}' at {data_file}", err=True)
        raise SystemExit(1)

    with open(data_file) as f:
        cards = json.load(f)
    card_count = len(cards)

    click.echo(f"Config loaded: {cfg.name}")
    click.echo(f"Cards: {card_count}")


@main.command()
@click.option("--results-dir", required=True, help="Path to results directory.")
def eval(results_dir: str) -> None:
    """Run evaluation (stub)."""
    click.echo(f"Eval stub: results_dir={results_dir}")


@main.command()
@click.option("--results-dir", required=True, help="Path to results directory.")
def score(results_dir: str) -> None:
    """Compute scores (stub)."""
    click.echo(f"Score stub: results_dir={results_dir}")


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
