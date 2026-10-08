"""Run details: a header of facts and tabs over the run's output, requests and workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, RichLog, Static, TabbedContent, TabPane

from silverquillm.monitor import (
    LogLine,
    RecordDetail,
    RequestCost,
    RunSummary,
    RunView,
    Stage,
    WorkspaceView,
    render_line,
)

from . import format as fmt
from .theme import Theme

MAX_LOG_LINES = 4000
SPARK_WIDTH = 60
COST_LABELS = {
    "uncached_input": "uncached in",
    "cache_read": "cache read",
    "cache_write": "cache write",
    "cache_write_1h": "cache write 1h",
    "output": "output",
}


@dataclass
class Shown:
    """What the details view currently shows, as the app last observed it."""

    run_id: str
    pinned: bool = False
    """Opened as one Run Record from history, which stays the record shown."""
    live: RunView | None = None
    summary: RunSummary | None = None
    """The applicable Run Record: header, requests and breakdown all come from it."""
    record_key: tuple[str, str] | None = None
    """``summary``'s identity; when it changes, the shown detail is obsolete."""
    last_record: RunSummary | None = None
    """The record that last applied while the run was live, kept once it leaves the live view."""
    detail: RecordDetail | None = None
    seq: int = 0
    lines: int = 0
    retained_loaded: bool = False
    """The retained logs are shown; they are read once, whether or not this host has them."""
    detail_ready: bool = False
    """The Run Record's detail is shown; until then every poll asks for it again."""
    requests: list[RequestCost] = field(default_factory=list)
    workspace: WorkspaceView | None = None


def header(shown: Shown, now: datetime, theme: Theme) -> Table:
    live, summary = shown.live, shown.summary
    table = Table.grid(padding=(0, 2), expand=True)
    table.add_column(ratio=3)
    table.add_column(ratio=2)
    badge = Text()
    if live is not None and live.run.stage is Stage.NEEDS_RECOVER:
        badge.append(
            f" {theme.glyph('needs_recover_badge')} ",
            style=f"{theme.style('needs_recover', bold=True)} reverse",
        )
    elif live is not None:
        badge.append(f" {theme.glyph('live')} ", style=f"{theme.style('live', bold=True)} reverse")
    else:
        badge.append(
            f" {theme.glyph('historical')} ", style=f"{theme.style('muted', bold=True)} reverse"
        )
    badge.append(f"  run {shown.run_id}", style=theme.style("muted"))
    candidate = live.run.candidate if live else summary.candidate if summary else None
    benchmark = live.run.benchmark if live else summary.benchmark if summary else None
    login = live.run.login_profile if live else summary.login_profile if summary else None
    left = Text()
    left.append_text(badge)
    left.append("\n")
    if candidate is not None:
        left.append(candidate.label, style=theme.style("title", bold=True))
        for label in candidate.secondary:
            left.append(f"  {label}", style=theme.style("muted"))
        left.append("\n")
    left.append_text(fmt.badge(benchmark, theme))
    left.append(f"{theme.glyph('sep')}{login or fmt.DASH}", style=theme.style("muted"))
    if summary is not None and summary.host_label:
        left.append(f"{theme.glyph('sep')}host {summary.host_label}", style=theme.style("muted"))
    if summary is not None and summary.recovery_of:
        left.append(
            f"{theme.glyph('sep')}recovers {summary.recovery_of[:8]}", style=theme.style("warn")
        )
    elif summary is not None and summary.execution_id != summary.run_id:
        left.append(
            f"{theme.glyph('sep')}execution {summary.execution_id[:8]}", style=theme.style("muted")
        )
    left.append("\n")
    if live is not None:
        run = live.run
        left.append_text(fmt.stage(run.stage, theme))
        left.append(
            f"  {fmt.duration(run.elapsed_seconds(now))} of {fmt.duration(run.budget_seconds)}  ",
            style=theme.style("text"),
        )
        left.append_text(fmt.bar(live.budget_fraction(now), 20, theme))
        if live.estimated_percent is not None:
            left.append(f"  est {live.estimated_percent:.0f}%", style=theme.style("accent"))
        left.append(f"\nstarted {fmt.when(run.started_at)}", style=theme.style("muted"))
        if run.stage in (Stage.NEEDS_RECOVER, Stage.UNKNOWN):
            left.append("\n")
            left.append_text(fmt.reasons(run, theme))
    elif summary is not None:
        left.append_text(fmt.status(summary.status, theme))
        duration = fmt.duration(summary.duration_seconds)
        left.append(
            f"  {duration} of {fmt.duration(summary.budget_seconds)}", style=theme.style("text")
        )
        left.append(f"\nran {fmt.when(summary.run_date)}", style=theme.style("muted"))
        if summary.excluded:
            left.append(
                f"\n{theme.glyph('excluded')} excluded: {summary.excluded}",
                style=theme.style("warn", bold=True),
            )
    detail = shown.detail
    if detail is not None and (detail.failure_stage or detail.error):
        left.append(
            f"\n{theme.glyph('error')} {detail.failure_stage or ''} {detail.error or ''}".rstrip(),
            style=theme.style("bad"),
        )
    right = Table.grid(padding=(0, 1))
    right.add_column(style=theme.style("muted"))
    right.add_column()
    if summary is not None:
        for name, label in (
            ("card_correctness", "target"),
            ("fdn_regression", "fdn"),
            ("engine_regression", "engine"),
        ):
            right.add_row(label, fmt.score(summary.scores.get(name), theme))
        cost = fmt.money(summary.estimated_cost, theme)
        if summary.estimated_cost is not None and not summary.cost_complete:
            completeness = summary.cost_completeness or "partial"
            cost.append(f" {completeness}", style=theme.style("muted"))
        if summary.unpriced_requests:
            cost.append(f" +{summary.unpriced_requests} unpriced", style=theme.style("muted"))
        right.add_row("cost", cost)
        right.add_row("turns", fmt.count(summary.agent_turns))
        right.add_row("tokens", fmt.count(summary.total_tokens))
    elif live is not None:
        spend = fmt.spend(
            live.cost,
            theme,
            recorded=live.cost_recorded,
            completeness=live.cost_completeness,
            conflicting=live.conflicting_requests,
        )
        right.add_row("cost", spend)
        right.add_row("requests", str(len(shown.requests)))
    if detail is not None and detail.breakdown:
        for name, (tokens, usd) in detail.breakdown.items():
            right.add_row(
                Text(COST_LABELS.get(name, name)),
                Text.assemble(fmt.count(tokens), " tok  ", fmt.money(usd, theme)),
            )
    table.add_row(left, right)
    return table


def activity_rows(line: LogLine, theme: Theme) -> list[Table]:
    """Each activity item as a row whose wrapped lines hang under its text, not its time."""
    rows = []
    stamp = fmt.when(line.at, with_day=False) if line.at else ""
    for item in render_line(line.text):
        role = "error" if item.failed else item.kind
        body = Text(style=theme.style(role))
        for done, entry in item.checklist:
            body.append(f"{theme.glyph('todo_done' if done else 'todo_open')} {entry}\n")
        body.append(item.text)
        body.rstrip()
        row = Table.grid(expand=True)
        row.add_column(width=6, no_wrap=True)
        row.add_column(width=2, no_wrap=True)
        row.add_column(ratio=1)
        row.add_row(
            Text(stamp, style=theme.style("muted")),
            Text(theme.glyph(item.kind), style=theme.style(role, bold=True)),
            body,
        )
        rows.append(row)
    return rows


class DetailsView(Vertical):
    def __init__(self, theme: Theme) -> None:
        super().__init__(id="details")
        self.theme_ = theme
        self.shown: Shown | None = None
        self.generation = 0
        """Bumped whenever the shown output restarts, so a fetch made before it is dropped."""

    def compose(self) -> ComposeResult:
        head = Static(id="detail-head", classes="pane")
        head.border_title = "RUN"
        yield head
        with TabbedContent(id="detail-tabs"):
            with TabPane("Activity", id="tab-activity"):
                yield RichLog(id="log-activity", max_lines=MAX_LOG_LINES, wrap=True)
            with TabPane("Stderr", id="tab-stderr"):
                yield RichLog(id="log-stderr", max_lines=MAX_LOG_LINES, wrap=True)
            with TabPane("Requests", id="tab-requests"):
                yield Static(id="request-spark")
                yield DataTable(id="requests-table", cursor_type="row")
            with TabPane("Workspace", id="tab-workspace"), Vertical():
                yield Static(id="workspace-note")
                with Horizontal():
                    yield DataTable(id="snapshots-table", cursor_type="row")
                    yield DataTable(id="commits-table", cursor_type="row")
            with TabPane("Raw", id="tab-raw"):
                yield RichLog(id="log-raw", max_lines=MAX_LOG_LINES, wrap=False)
        yield Static(
            "open a run from the dashboard or history", classes="empty", id="details-empty"
        )

    def on_mount(self) -> None:
        requests = self.query_one("#requests-table", DataTable)
        for label in ("time", "model", "input", "cached", "cache write", "output", "cost"):
            requests.add_column(label)
        snapshots = self.query_one("#snapshots-table", DataTable)
        for label in ("snapshot", "kind", "files", "Δ", "changed"):
            snapshots.add_column(label)
        commits = self.query_one("#commits-table", DataTable)
        for label in ("time", "action", "message", "commit"):
            commits.add_column(label)
        self._show_empty(True)

    def _show_empty(self, empty: bool) -> None:
        self.query_one("#details-empty").display = empty
        self.query_one("#detail-head").display = not empty
        self.query_one("#detail-tabs").display = not empty

    def open(self, run_id: str, *, pinned: bool = False) -> Shown:
        """Show another run: nothing of the previous run may remain under its header."""
        self.generation += 1
        self.shown = Shown(run_id, pinned=pinned)
        for log in self.query(RichLog):
            log.clear()
        theme = self.theme_
        loading = Text(f"{theme.glyph('loading')} loading", style=theme.style("muted"))
        head = self.query_one("#detail-head", Static)
        head.update(Text.assemble(Text(f"run {run_id}  ", style=theme.style("muted")), loading))
        head.border_title = "RUN"
        for table in ("#requests-table", "#snapshots-table", "#commits-table"):
            self.query_one(table, DataTable).clear()
        self.query_one("#request-spark", Static).update(loading)
        self.query_one("#workspace-note", Static).update(loading)
        self._show_empty(False)
        return self.shown

    def clear_requests(self) -> None:
        """The applicable record changed: its requests are loading and the old ones are gone."""
        theme = self.theme_
        self.query_one("#requests-table", DataTable).clear()
        self.query_one("#request-spark", Static).update(
            Text(f"{theme.glyph('loading')} loading", style=theme.style("muted"))
        )

    def show_requests_unavailable(self) -> None:
        """A recorded run whose Run Record could not be read (yet): say so, show nothing."""
        if self.shown is None:
            return
        self.query_one("#requests-table", DataTable).clear()
        self.query_one("#request-spark", Static).update(
            Text("the Run Record is not readable yet", style=self.theme_.style("muted"))
        )

    def restart_output(self) -> None:
        """A run that just left the live view: its output now comes from retained logs."""
        if self.shown is None:
            return
        for log in self.query(RichLog):
            log.clear()
        self.generation += 1
        self.shown.seq = 0
        self.shown.lines = 0
        self.shown.retained_loaded = False

    def show_header(self, now: datetime) -> None:
        if self.shown is None:
            return
        head = self.query_one("#detail-head", Static)
        head.update(header(self.shown, now, self.theme_))
        live = self.shown.live
        if live is not None and live.run.stage is Stage.NEEDS_RECOVER:
            head.border_title = "UNRECORDED RUN"
        else:
            head.border_title = "LIVE RUN" if live else "RECORDED RUN"

    def append_output(self, lines: list[LogLine]) -> None:
        if self.shown is None or not lines:
            return
        self.shown.seq = max(self.shown.seq, max(line.seq for line in lines))
        self.shown.lines += len(lines)
        theme = self.theme_
        # Each stream keeps its own tail, so a flood of stderr never evicts stdout's evidence;
        # a retained log can hold far more than a tab keeps, so only what stays is rendered.
        stdout = [line for line in lines if line.stream != "stderr"][-MAX_LOG_LINES:]
        stderr = self.query_one("#log-stderr", RichLog)
        for line in [line for line in lines if line.stream == "stderr"][-MAX_LOG_LINES:]:
            stderr.write(Text(line.text, style=theme.style("text")), expand=True)
        activity = self.query_one("#log-activity", RichLog)
        raw = self.query_one("#log-raw", RichLog)
        for line in stdout:
            for row in activity_rows(line, theme):
                activity.write(row, expand=True)
            raw.write(Text(line.text, style=theme.style("muted")))

    def show_requests(self, requests: list[RequestCost], now: datetime) -> None:
        if self.shown is None:
            return
        theme = self.theme_
        self.shown.requests = requests
        table = self.query_one("#requests-table", DataTable)
        table.clear()
        for request in requests[-2000:]:
            tokens = request.tokens
            table.add_row(
                fmt.when(_from_ms(request.timestamp_ms), with_day=False),
                Text(request.model or fmt.DASH, style=theme.style("text")),
                fmt.count(tokens.get("input_tokens")),
                fmt.count(tokens.get("cached_input_tokens")),
                fmt.count(tokens.get("cache_write_input_tokens")),
                fmt.count(tokens.get("output_tokens")),
                fmt.money(request.usd, theme)
                if request.usd is not None
                else Text("unpriced", style=theme.style("muted")),
            )
        points = [
            (row.timestamp_ms, row.usd)
            for row in requests
            if row.usd is not None and row.timestamp_ms
        ]
        spark = Text("spend over the run  ", style=theme.style("muted"))
        spark.append_text(fmt.sparkline(sorted(points), SPARK_WIDTH, theme))
        priced = sum(1 for row in requests if row.usd is not None)
        spark.append(f"  {priced}/{len(requests)} priced", style=theme.style("muted"))
        self.query_one("#request-spark", Static).update(spark)

    def show_workspace(self, view: WorkspaceView) -> None:
        if self.shown is None:
            return
        theme = self.theme_
        self.shown.workspace = view
        note = "" if view.snapshots or view.commits else "no workspace evidence on this host"
        self.query_one("#workspace-note", Static).update(Text(note, style=theme.style("muted")))
        snapshots = self.query_one("#snapshots-table", DataTable)
        snapshots.clear()
        for entry in view.snapshots:
            delta = "" if entry.files_delta in (None, 0) else f"{entry.files_delta:+d}"
            snapshots.add_row(
                Text(f"{theme.glyph('snapshot')} {fmt.when(entry.captured_at, with_day=False)}"),
                Text(entry.kind or ""),
                fmt.count(entry.files),
                delta,
                Text("changed", style=theme.style("accent")) if entry.changed else "",
            )
        commits = self.query_one("#commits-table", DataTable)
        commits.clear()
        for entry in view.commits:
            commits.add_row(
                fmt.when(entry.at, with_day=False),
                Text(f"{theme.glyph('commit')} {entry.action}", style=theme.style("tool")),
                Text(entry.message[:120]),
                Text(entry.commit, style=theme.style("muted")),
            )


def _from_ms(stamp: int) -> datetime | None:
    from datetime import UTC

    if not stamp:
        return None
    try:
        return datetime.fromtimestamp(stamp / 1000, UTC)
    except (OverflowError, OSError, ValueError):
        return None
