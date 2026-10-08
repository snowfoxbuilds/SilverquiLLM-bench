"""The dashboard: status across the top, running runs bottom left, the queue bottom right."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Static

from silverquillm.monitor import MonitorSnapshot, ProfileView, RunView, Stage

from . import format as fmt
from .theme import Theme
from .widgets import ClickTable

STAGE_ORDER = {
    Stage.NEEDS_RECOVER: 0,
    Stage.UNKNOWN: 1,
    Stage.RUNNING: 2,
    Stage.STARTING: 3,
    Stage.GRADING: 4,
    Stage.RECORDING: 5,
}
LOCATION_LABELS = {
    "results_repo": "results",
    "batches_dir": "queue",
    "runs_dir": "runs",
    "state_root": "state",
}
NARROW = 150
"""Below this many columns the dashboard compacts, see MonitorApp.on_resize."""
BAR_WIDTH = 12
SPARK_WIDTH = 16
CANDIDATE_WIDTH = 36
REASONS_WIDTH = 44
WEEKLY_BAR = 10


class RunChosen(Message):
    """The operator picked a run to open in run details."""

    def __init__(self, run_id: str, *, pinned: bool = False) -> None:
        super().__init__()
        self.run_id = run_id
        self.pinned = pinned
        """Opened as one Run Record from history: details keep showing that record."""


def _short(path) -> str:
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home) :] if text.startswith(home) else text


class StatusPane(Horizontal):
    def __init__(self, theme: Theme) -> None:
        super().__init__(id="status", classes="pane")
        self.theme_ = theme
        self.border_title = "STATUS"

    def compose(self) -> ComposeResult:
        yield Static(id="where")
        yield Static(id="counts")
        yield Static(id="pools")

    def show(self, snapshot: MonitorSnapshot) -> None:
        theme = self.theme_
        self.query_one("#where", Static).update(self._where(snapshot, theme))
        self.query_one("#counts", Static).update(self._counts(snapshot, theme))
        compact = self.app.size.width < NARROW
        self.query_one("#pools", Static).update(self._pools(snapshot, theme, compact=compact))

    @staticmethod
    def _where(snapshot: MonitorSnapshot, theme: Theme) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style=theme.style("muted"), no_wrap=True, min_width=7)
        table.add_column(overflow="ellipsis", no_wrap=True)
        muted = theme.style("muted")
        for key, label in LOCATION_LABELS.items():
            location = snapshot.locations.get(key)
            if location is None or location.path is None:
                table.add_row(label, Text("unset", style=theme.style("bad", bold=True)))
            else:
                where = Text(_short(location.path))
                where.append(f" ({location.source})", style=muted)
                table.add_row(label, where)
        repo = snapshot.repo
        fetched = Text(fmt.ago(snapshot.taken_at - repo.last_fetch) if repo.last_fetch else "never")
        if repo.behind:
            fetched.append(f" · {repo.behind} behind", style=theme.style("warn", bold=True))
        elif repo.behind == 0:
            fetched.append(" · up to date", style=theme.style("good"))
        table.add_row("fetch", fetched)
        table.add_row("host", Text(snapshot.host_label or "unlabelled", style=muted))
        for problem in (snapshot.config_error, snapshot.docker_error, snapshot.exclusion_error):
            if problem:
                table.add_row(Text(theme.glyph("problem")), Text(problem, style=theme.style("bad")))
        return table

    @staticmethod
    def _counts(snapshot: MonitorSnapshot, theme: Theme) -> Text:
        counts = snapshot.counts
        text = Text()
        rows = (
            ("running", counts.live, "live", "running"),
            ("queued", counts.queued, "queued", "accent"),
            ("finished", counts.finished_recent, "this week", "good"),
        )
        for glyph, value, label, role in rows:
            text.append(f"{theme.glyph(glyph)} ", style=theme.style(role))
            text.append(f"{value:>4}", style=theme.style(role, bold=True))
            text.append(f" {label}\n", style=theme.style("muted"))
        text.append(f"  {counts.finished_total:>4} all time", style=theme.style("muted"))
        return text

    @staticmethod
    def _pools(snapshot: MonitorSnapshot, theme: Theme, *, compact: bool = False) -> Table:
        """Each pool's Login Profiles; a compact pane drops the usage bars for the text."""
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True, overflow="ellipsis", min_width=20)
        if not compact:
            table.add_column(no_wrap=True)
        table.add_column(no_wrap=True, overflow="ellipsis")
        pools: dict[str, list[ProfileView]] = defaultdict(list)
        for view in snapshot.profiles:
            pools[view.status.provider].append(view)
        if not pools:
            table.add_row(Text("no Login Profiles enrolled", style=theme.style("muted")))
        for provider in sorted(pools):
            views = pools[provider]
            role = fmt.provider_role(provider)
            free = sum(1 for view in views if view.status.busy is False)
            title = Text(f"{provider.upper()} pool", style=theme.style(role, bold=True))
            untapped = Text(f"{free}/{len(views)} untapped", style=theme.style("muted"))
            table.add_row(title, untapped) if compact else table.add_row(title, "", untapped)
            for view in sorted(views, key=lambda item: item.status.slot):
                name, bar, weekly = StatusPane._profile(view, snapshot.taken_at, theme)
                table.add_row(name, weekly) if compact else table.add_row(name, bar, weekly)
        return table

    @staticmethod
    def _profile(view: ProfileView, now: datetime, theme: Theme) -> tuple:
        status = view.status
        if status.pending:
            mark = Text(theme.glyph("pending"), style=theme.style("bad", bold=True))
        elif status.busy is None:
            mark = Text(theme.glyph("lock_unknown"), style=theme.style("muted"))
        elif status.busy:
            mark = Text(
                theme.glyph("tapped"),
                style=theme.style(fmt.provider_role(status.provider), bold=True),
            )
        else:
            mark = Text(theme.glyph("untapped"), style=theme.style("muted"))
        name = Text(f"{mark.plain} ", style=mark.style)
        name.append(status.slot, style=theme.style("text" if status.busy else "muted"))
        if status.pending_run:
            # The run that still owns this login's settlement; recovering it frees the profile.
            name.append(
                f"{theme.glyph('sep')}{theme.glyph('pending')} {status.pending_run[:8]}",
                style=theme.style("bad"),
            )
        percent = view.weekly.percent / 100 if view.weekly else None
        return name, fmt.bar(percent, WEEKLY_BAR, theme), fmt.weekly(view.weekly, now, theme)


class RunningPane(Vertical):
    def __init__(self, theme: Theme) -> None:
        super().__init__(id="running", classes="pane")
        self.theme_ = theme
        self.border_title = f"{theme.glyph('running')} RUNNING"
        self._order: list[str] = []

    def compose(self) -> ComposeResult:
        table = ClickTable(id="running-table", cursor_type="row")
        for label, key in (
            ("stage", "stage"),
            ("benchmark · login", "where"),
            ("candidate", "candidate"),
            ("progress", "progress"),
            ("spend", "spend"),
        ):
            table.add_column(label, key=key)
        yield table
        yield Static("no runs on this host", classes="empty", id="running-empty")

    def show(self, snapshot: MonitorSnapshot) -> None:
        theme = self.theme_
        table = self.query_one(DataTable)
        runs = sorted(
            snapshot.running,
            key=lambda view: (STAGE_ORDER.get(view.run.stage, 9), view.run.run_id),
        )
        self.query_one("#running-empty").display = not runs
        table.display = bool(runs)
        self.border_subtitle = f"{len(runs)} unfinished on this host"
        selected = (
            self._order[table.cursor_row] if 0 <= table.cursor_row < len(self._order) else None
        )
        table.clear()
        self._order = []
        now = snapshot.taken_at
        for view in runs:
            table.add_row(*self._cells(view, now, theme), key=view.run.run_id, height=2)
            self._order.append(view.run.run_id)
        if selected in self._order:
            table.move_cursor(row=self._order.index(selected), animate=False)

    @staticmethod
    def _cells(view: RunView, now: datetime, theme: Theme) -> tuple:
        """Two lines per run: what and where on top, how far and how much below."""
        run = view.run
        muted = theme.style("muted")
        elapsed = run.elapsed_seconds(now)
        stage = fmt.stage(run.stage, theme)
        stage.append(f"\n  {fmt.duration(elapsed)}", style=theme.style("text"))
        where = fmt.badge(run.benchmark, theme)
        login = run.login_profile.partition("/")[2] if run.login_profile else fmt.DASH
        where.append(
            f"\n{theme.glyph('tapped')} {login}", style=theme.style(fmt.provider_role(run.provider))
        )
        candidate = Text(run.candidate.label, style=theme.style("text", bold=True))
        candidate.truncate(CANDIDATE_WIDTH, overflow="ellipsis")
        if run.stage is Stage.NEEDS_RECOVER:
            candidate.stylize(theme.style("needs_recover"))
        candidate.append("\n" + "  ".join((*run.candidate.secondary, run.run_id[:8])), style=muted)
        if run.stage in (Stage.NEEDS_RECOVER, Stage.UNKNOWN):
            # Its budget no longer matters; why it is stuck, and whether it still runs, does.
            progress = fmt.reasons(run, theme)
            progress.truncate(REASONS_WIDTH, overflow="ellipsis")
        else:
            progress = fmt.bar(view.budget_fraction(now), BAR_WIDTH, theme)
        if view.estimated_percent is not None:
            progress.append(
                f" {theme.glyph('estimated')}{view.estimated_percent:.0f}%",
                style=theme.style("accent", bold=True),
            )
        budget = fmt.short_duration(run.budget_seconds) if run.budget_seconds else fmt.DASH
        fraction = view.budget_fraction(now)
        used = f" · {fraction * 100:.0f}%" if fraction is not None else ""
        progress.append(f"\n{fmt.short_duration(elapsed)} of {budget}{used}", style=muted)
        spend = fmt.spend(
            view.cost,
            theme,
            recorded=view.cost_recorded,
            completeness=view.cost_completeness,
            conflicting=view.conflicting_requests,
        )
        if view.unpriced_requests:
            spend.append(f" +{view.unpriced_requests}?", style=muted)
        spend.append("\n")
        stamp = int(now.timestamp() * 1000)
        spend.append_text(fmt.sparkline(view.request_costs, SPARK_WIDTH, theme, until_ms=stamp))
        return stage, where, candidate, progress, spend

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if event.row_key.value:
            self.post_message(RunChosen(event.row_key.value))


class QueuedPane(VerticalScroll):
    def __init__(self, theme: Theme) -> None:
        super().__init__(id="queued", classes="pane")
        self.theme_ = theme
        self.border_title = f"{theme.glyph('queued')} QUEUED"

    def compose(self) -> ComposeResult:
        yield Static(id="queue-body")

    def show(self, snapshot: MonitorSnapshot) -> None:
        theme = self.theme_
        muted = theme.style("muted")
        lines: list[Text] = []
        total = 0
        for batch in snapshot.queued:
            if batch.status == "done" and not batch.runs:
                continue
            lines.append(
                Text(f"{theme.glyph('batch')} {batch.batch}", style=theme.style("title", bold=True))
            )
            state = Text("  ")
            if batch.needs_ack:
                state.append(theme.glyph("needs_ack"), style=theme.style("warn", bold=True))
            elif batch.not_before is not None and batch.not_before > snapshot.taken_at:
                state.append(
                    fmt.until(batch.not_before, snapshot.taken_at), style=theme.style("accent")
                )
            elif batch.error:
                state.append(batch.error, style=theme.style("bad"))
            else:
                state.append(batch.status, style=muted)
            state.append(f"{theme.glyph('sep')}{batch.started}/{batch.total} started", style=muted)
            lines.append(state)
            for queued in batch.runs:
                total += 1
                run = Text("  ")
                run.append_text(fmt.badge(queued.benchmark, theme))
                run.append(
                    f"{theme.glyph('sep')}{fmt.short_duration(queued.budget_seconds)}", style=muted
                )
                lines.append(run)
                lines.append(Text(f"    {queued.candidate.label}", style=theme.style("text")))
        if not lines:
            lines.append(Text("nothing queued", style=muted))
        self.border_subtitle = f"{total} runs"
        # One line per entry: a long candidate is cut with an ellipsis rather than wrapped.
        width = max(8, self.scrollable_content_region.width or 40)
        for line in lines:
            line.truncate(width, overflow="ellipsis")
        self.query_one("#queue-body", Static).update(Text("\n").join(lines))


class DashboardView(Vertical):
    def __init__(self, theme: Theme) -> None:
        super().__init__(id="dashboard")
        self.theme_ = theme

    def compose(self) -> ComposeResult:
        yield StatusPane(self.theme_)
        with Horizontal(id="lower"):
            yield RunningPane(self.theme_)
            yield QueuedPane(self.theme_)

    def show(self, snapshot: MonitorSnapshot) -> None:
        self.query_one(StatusPane).show(snapshot)
        self.query_one(RunningPane).show(snapshot)
        self.query_one(QueuedPane).show(snapshot)
