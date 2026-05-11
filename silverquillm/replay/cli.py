"""CLI subcommand for replay validation.

Provides ``benchmark validate <replay_path_or_dir>`` for running the
replay validation pipeline and producing summary/report output.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import click

from silverquillm.replay.executor import ReplayExecutor, load_card_id_map
from silverquillm.replay.parser import parse_replay
from silverquillm.replay.validation import (
    Divergence,
    DivergenceType,
    ValidationReport,
    validate_replay,
)


def _make_verbose_callback():
    """Return a callback for per-step verbose output."""
    def callback(step_index: int, snapshot_id: int, action_desc: str, result_desc: str) -> None:
        click.echo(f"  Step {step_index}: gsId={snapshot_id} action={action_desc} -> {result_desc}")
    return callback


def _is_replay_file(path: Path) -> bool:
    """Return True if this JSON file is a game replay (not metadata)."""
    name = path.name
    return (
        name != "card_id_map.json"
        and name != "event_details.json"
        and not name.endswith("_info.json")
    )


def _collect_replay_files(path: Path) -> list[Path]:
    """Collect replay JSON files from a path (file or directory).

    Searches recursively so that a set directory like data/replays/fdn
    finds replays nested under per-draft subdirectories.
    """
    if path.is_file():
        return [path]
    elif path.is_dir():
        return sorted(f for f in path.rglob("*.json") if _is_replay_file(f))
    return []


def _replay_contains_cards(
    replay_path: Path,
    card_names: list[str],
    card_id_map: dict[int, str],
) -> bool:
    """Check if a replay file contains any of the specified card names.

    Loads the raw JSON and checks if any grpId in the replay maps to
    one of the requested card names.
    """
    try:
        with open(replay_path) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    # Collect all grpIds from events
    lower_names = [n.lower() for n in card_names]
    for event in raw.get("events", []):
        gsm = event.get("gameStateMessage", {})
        for obj in gsm.get("gameObjects", []):
            grp_id = obj.get("grpId", 0)
            name = card_id_map.get(grp_id, "").lower()
            if name and name in lower_names:
                return True
    return False


def _aggregate_reports(
    reports: list[ValidationReport],
    card_id_map: dict[int, str],
) -> dict[str, Any]:
    """Aggregate multiple ValidationReports into a summary dict."""
    games_attempted = len(reports)
    games_completed = sum(
        1 for r in reports if r.divergence_count == 0
    )
    total_divergences = sum(r.divergence_count for r in reports)
    games_with_divergence = sum(
        1 for r in reports if r.divergence_count > 0
    )
    divergence_rate = (
        games_with_divergence / games_attempted if games_attempted > 0 else 0.0
    )

    # Top divergence causes (by DivergenceType)
    cause_counter: Counter[str] = Counter()
    for r in reports:
        for dtype, count in r.divergences_by_type.items():
            cause_counter[dtype.value] += count
    top_causes = [
        {"cause": cause, "count": count}
        for cause, count in cause_counter.most_common(10)
    ]

    # Per-card divergence rates (aggregated across all reports)
    card_div_counts: Counter[int] = Counter()
    card_appearances: Counter[int] = Counter()
    for r in reports:
        for d in r.divergences:
            for grp_id in d.involved_grp_ids:
                card_div_counts[grp_id] += 1
        for grp_id, count in r.card_appearances.items():
            card_appearances[grp_id] += count

    per_card_rates: dict[str, float] = {}
    for grp_id, div_count in card_div_counts.items():
        appearances = card_appearances.get(grp_id, div_count)
        rate = div_count / appearances if appearances > 0 else 0.0
        card_name = card_id_map.get(grp_id, f"grpId_{grp_id}")
        per_card_rates[card_name] = round(rate, 4)

    return {
        "games_attempted": games_attempted,
        "games_completed_without_divergence": games_completed,
        "divergence_rate": round(divergence_rate, 4),
        "total_divergences": total_divergences,
        "top_divergence_causes": top_causes,
        "per_card_rates": per_card_rates,
        "divergences": [
            {
                "game_state_id": d.game_state_id,
                "type": d.divergence_type.value,
                "description": d.description,
                "involved_grp_ids": d.involved_grp_ids,
            }
            for r in reports
            for d in r.divergences
        ],
    }


@click.command("validate")
@click.argument("replay_path")
@click.option(
    "--cards",
    "card_filter",
    default=None,
    help="Comma-separated card names to filter replays.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Show each action and state comparison.",
)
@click.option(
    "--report",
    "report_path",
    default=None,
    type=click.Path(),
    help="Output JSON report file path.",
)
@click.option(
    "--stop-on-divergence",
    is_flag=True,
    default=False,
    help="Halt at first mismatch for debugging.",
)
def validate(
    replay_path: str,
    card_filter: str | None,
    verbose: bool,
    report_path: str | None,
    stop_on_divergence: bool,
) -> None:
    """Validate replay files against the engine.

    REPLAY_PATH can be a single JSON replay file or a directory of replay
    JSON files.
    """
    path = Path(replay_path)
    if not path.exists():
        raise click.ClickException(f"Path not found: {replay_path}")

    # Load card ID map
    card_id_map = load_card_id_map()

    # Collect replay files
    replay_files = _collect_replay_files(path)

    if not replay_files:
        raise click.ClickException(f"No replay JSON files found at: {replay_path}")

    # Apply card name filter
    if card_filter:
        card_names = [n.strip() for n in card_filter.split(",")]
        replay_files = [
            f for f in replay_files
            if _replay_contains_cards(f, card_names, card_id_map)
        ]
        if not replay_files:
            click.echo(f"No replays found containing cards: {card_filter}")
            return

    # Process each replay
    reports: list[ValidationReport] = []
    stopped_early = False

    for replay_file in replay_files:
        if verbose:
            click.echo(f"\n--- Validating: {replay_file.name} ---")

        try:
            replay = parse_replay(replay_file, card_id_map=card_id_map)
        except Exception as exc:
            click.echo(f"  Error parsing {replay_file.name}: {exc}", err=True)
            # Count parse failures as attempted (and failed) games
            failed_report = ValidationReport(
                total_snapshots=0,
                successful_comparisons=0,
                divergences=[
                    Divergence(
                        game_state_id=0,
                        divergence_type=DivergenceType.ENGINE_ERROR,
                        description=f"Parse error: {exc}",
                        involved_grp_ids=[],
                    )
                ],
            )
            reports.append(failed_report)
            continue

        executor = ReplayExecutor(
            replay=replay,
            card_id_map=card_id_map,
        )

        report = validate_replay(
            executor,
            card_id_map,
            stop_on_first=stop_on_divergence,
            step_callback=_make_verbose_callback() if verbose else None,
        )
        reports.append(report)

        if verbose:
            click.echo(report.summary())

        if stop_on_divergence and report.divergence_count > 0:
            first = report.first_divergence_point
            click.echo(
                f"\nStopped on divergence in {replay_file.name}: {first}",
                err=True,
            )
            stopped_early = True
            break

    # Build aggregate summary
    summary = _aggregate_reports(reports, card_id_map)

    # Print summary
    click.echo(f"\n=== Validation Summary ===")
    click.echo(f"Games attempted: {summary['games_attempted']}")
    click.echo(
        f"Games completed without divergence: "
        f"{summary['games_completed_without_divergence']}"
    )
    click.echo(f"Divergence rate: {summary['divergence_rate']}")

    if summary["top_divergence_causes"]:
        click.echo("Top divergence causes:")
        for cause in summary["top_divergence_causes"]:
            click.echo(f"  {cause['cause']}: {cause['count']}")

    if summary["per_card_rates"]:
        click.echo("Per-card divergence rates:")
        sorted_rates = sorted(
            summary["per_card_rates"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for card_name, rate in sorted_rates[:10]:
            click.echo(f"  {card_name}: {rate:.4f}")

    if stopped_early:
        click.echo("\n(Stopped early due to --stop-on-divergence)")

    # Write JSON report if requested
    if report_path:
        report_out = Path(report_path)
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(summary, indent=2))
        click.echo(f"\nReport written to: {report_out}")
