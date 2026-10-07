"""Run Records and Exclusions read straight from the Results Repo clone, cached by file state.

The derived ``runs.jsonl`` index is never maintained, so it is never read; each record is
parsed once and kept as a small summary until its files change (RUN-MONITORING.md,
What the monitor reads).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from silverquillm.karn.exclusions import ExclusionError, load_exclusions

from ._read import instant, mapping, read_json
from .candidates import CandidateDisplay, candidate_display

DIMENSIONS = ("card_correctness", "fdn_regression", "engine_regression")
GIT_TIMEOUT = 5


@dataclass(frozen=True)
class Score:
    evaluated: bool
    pass_rate: float | None
    passed: int | None
    total: int | None


@dataclass(frozen=True)
class UsageReading:
    """A provider's report of a Login Profile's weekly window."""

    provider: str
    utilization_percent: float
    window_minutes: int
    resets_at: datetime
    observed_at: datetime | None
    bound: datetime | None = None
    """When the reading's time is unknown, the latest it can have been taken."""

    @property
    def effective_at(self) -> datetime | None:
        return self.observed_at or self.bound


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    candidate_hash: str
    schema_version: int | None
    benchmark: str | None
    run_date: datetime | None
    status: str | None
    started_at: datetime | None
    stopped_at: datetime | None
    budget_seconds: int | None
    scores: dict[str, Score]
    estimated_cost: Decimal | None
    cost_complete: bool
    agent_turns: int | None
    total_tokens: int | None
    login_profile: str | None
    host_label: str | None
    candidate: CandidateDisplay
    request_costs: tuple[tuple[int, Decimal], ...]
    """``(timestamp_ms, usd)`` of each priced request."""
    usage_reading: UsageReading | None
    path: Path
    excluded: str | None = None
    """The Exclusion's reason code."""

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None or self.stopped_at is None:
            return None
        return max(0.0, (self.stopped_at - self.started_at).total_seconds())

    @property
    def target(self) -> Score | None:
        return self.scores.get("card_correctness")


def _value(measurement: Any) -> Any:
    return mapping(measurement).get("value")


def _int(value: Any) -> int | None:
    return value if type(value) is int else None


def _decimal(value: Any) -> Decimal | None:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def _request_costs(measurements: dict) -> tuple[tuple[int, Decimal], ...]:
    prices = {
        row.get("response_id"): _decimal(row.get("usd"))
        for row in measurements.get("request_prices") or []
        if isinstance(row, dict)
    }
    costs = []
    for request in measurements.get("requests") or []:
        if not isinstance(request, dict):
            continue
        usd, stamp = prices.get(request.get("response_id")), _int(request.get("timestamp_ms"))
        if usd is not None and stamp:
            costs.append((stamp, usd))
    return tuple(sorted(costs))


def _reading(measurements: dict, stopped_at: datetime | None) -> UsageReading | None:
    value = _value(measurements.get("subscription_usage"))
    if not isinstance(value, dict):
        return None
    percent, resets_at = value.get("utilization_percent"), instant(value.get("resets_at"))
    if (
        not isinstance(percent, int | float)
        or isinstance(percent, bool)
        or resets_at is None
        or value.get("provider") not in ("claude", "codex")
    ):
        return None
    return UsageReading(
        value["provider"],
        float(percent),
        _int(value.get("window_minutes")) or 0,
        resets_at,
        instant(value.get("observed_at")),
        stopped_at,
    )


def _score(value: Any) -> Score:
    value = mapping(value)
    rate = value.get("pass_rate")
    return Score(
        value.get("evaluated") is True,
        float(rate) if isinstance(rate, int | float) and not isinstance(rate, bool) else None,
        _int(value.get("tests_passed")),
        _int(value.get("tests_total")),
    )


def summarize(manifest: Any, scores: Any, path: Path) -> RunSummary | None:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("run_id"), str):
        return None
    metadata = mapping(manifest.get("run_metadata"))
    execution = mapping(metadata.get("execution"))
    measurements = mapping(metadata.get("measurements"))
    provenance = mapping(metadata.get("provenance"))
    candidate_hash = manifest.get("candidate_hash") or path.parent.name
    stopped_at = instant(execution.get("stopped_at"))
    usage = _value(measurements.get("usage"))
    cost = mapping(measurements.get("estimated_cost"))
    login = metadata.get("login_profile")
    host_label = provenance.get("host_label")
    return RunSummary(
        run_id=manifest["run_id"],
        candidate_hash=str(candidate_hash),
        schema_version=_int(manifest.get("schema_version")),
        benchmark=manifest.get("benchmark") if isinstance(manifest.get("benchmark"), str) else None,
        run_date=instant(metadata.get("run_date") or manifest.get("run_date")),
        status=execution.get("status") if isinstance(execution.get("status"), str) else None,
        started_at=instant(execution.get("started_at")),
        stopped_at=stopped_at,
        budget_seconds=_int(manifest.get("budget_seconds")),
        scores={name: _score(mapping(scores).get(name)) for name in DIMENSIONS},
        estimated_cost=_decimal(cost.get("value")),
        cost_complete=cost.get("completeness") == "complete",
        agent_turns=_int(_value(mapping(measurements.get("agent_turns")).get("total"))),
        total_tokens=_int(mapping(usage).get("total_tokens")),
        login_profile=login if isinstance(login, str) else None,
        host_label=host_label if isinstance(host_label, str) else None,
        candidate=candidate_display(
            metadata.get("candidate_definition"),
            str(candidate_hash),
            provenance.get("recipe_revision"),
        ),
        request_costs=_request_costs(measurements),
        usage_reading=_reading(measurements, stopped_at),
        path=path,
    )


def _state(path: Path) -> tuple[int, int] | None:
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


class HistoryStore:
    """The Results Repo's records, re-read only where a record's files changed."""

    def __init__(self, results_repo: Path | None):
        self.results_repo = Path(results_repo) if results_repo is not None else None
        self._cache: dict[Path, tuple[tuple, RunSummary | None]] = {}
        self._exclusions: dict[str, str] = {}
        self._exclusions_key: tuple | None = None
        self.exclusion_error: str | None = None

    def _record_dirs(self) -> list[Path]:
        results = self.results_repo / "results"
        found = []
        try:
            candidates = [
                entry for entry in os.scandir(results) if entry.is_dir(follow_symlinks=False)
            ]
        except OSError:
            return found
        for candidate in candidates:
            try:
                runs = list(os.scandir(candidate.path))
            except OSError:
                continue
            found.extend(
                Path(run.path)
                for run in runs
                if run.name != "candidate" and run.is_dir(follow_symlinks=False)
            )
        return found

    def _refresh_exclusions(self) -> None:
        root = self.results_repo / "exclusions"
        try:
            key = tuple(sorted((str(path), _state(path)) for path in root.glob("*/*.json")))
        except OSError:
            key = ()
        if key == self._exclusions_key:
            return
        self._exclusions_key = key
        try:
            loaded = load_exclusions(self.results_repo)
        except ExclusionError as error:
            self.exclusion_error = str(error)
            return
        self.exclusion_error = None
        self._exclusions = {run_id: exclusion.reason for run_id, exclusion in loaded.items()}

    def runs(self) -> list[RunSummary]:
        """Every readable record, newest first, with its Exclusion's reason when excluded."""
        if self.results_repo is None:
            return []
        self._refresh_exclusions()
        seen, summaries = set(), []
        for run_dir in self._record_dirs():
            manifest, scores = run_dir / "manifest.json", run_dir / "scores.json"
            key = (_state(manifest), _state(scores))
            seen.add(run_dir)
            cached = self._cache.get(run_dir)
            if cached is None or cached[0] != key:
                summary = summarize(read_json(manifest), read_json(scores), run_dir)
                cached = (key, summary)
                self._cache[run_dir] = cached
            if cached[1] is not None:
                summaries.append(cached[1])
        for gone in set(self._cache) - seen:
            del self._cache[gone]
        result = [
            _with_exclusion(summary, self._exclusions.get(summary.run_id)) for summary in summaries
        ]
        return sorted(
            result,
            key=lambda run: (
                run.run_date.timestamp() if run.run_date else float("-inf"),
                run.run_id,
            ),
            reverse=True,
        )


def _with_exclusion(summary: RunSummary, reason: str | None) -> RunSummary:
    return summary if summary.excluded == reason else replace(summary, excluded=reason)


@dataclass(frozen=True)
class RepoFreshness:
    last_fetch: datetime | None
    behind: int | None
    """Commits on the remote-tracking branch not in HEAD, by local refs only."""


def _git(repo: Path, *arguments: str) -> str | None:
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            capture_output=True,
            timeout=GIT_TIMEOUT,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.decode(errors="replace").strip() if result.returncode == 0 else None


def repo_freshness(results_repo: Path | None) -> RepoFreshness:
    """When the clone last fetched and how far it trails; never contacts the remote."""
    if results_repo is None:
        return RepoFreshness(None, None)
    fetch_head = _git(
        results_repo, "rev-parse", "--path-format=absolute", "--git-path", "FETCH_HEAD"
    )
    last_fetch = None
    if fetch_head:
        try:
            last_fetch = datetime.fromtimestamp(os.stat(fetch_head).st_mtime).astimezone()
        except OSError:
            last_fetch = None
    behind = _git(results_repo, "rev-list", "--count", "HEAD..@{upstream}")
    return RepoFreshness(last_fetch, int(behind) if behind and behind.isdigit() else None)
