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
}
LOCATION_LABELS = {
    "results_repo": "results",
    "batches_dir": "queue",
    "runs_dir": "runs",
    "state_root": "state",
}
BAR_WIDTH = 14
SPARK_WIDTH = 20
WEEKLY_BAR = 10


class RunChosen(Message):
    """The operator picked a run to open in run details."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id


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
        self.query_one("#pools", Static).update(self._pools(snapshot, theme))

    @staticmethod
    def _where(snapshot: MonitorSnapshot, theme: Theme) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style=theme.style("muted"))
        table.add_column()
        table.add_column(style=theme.style("muted"))
        for key, label in LOCATION_LABELS.items():
            location = snapshot.locations.get(key)
            if location is None or location.path is None:
                table.add_row(label, Text("unset", style=theme.style("bad", bold=True)), "")
            else:
                table.add_row(label, _short(location.path), location.source)
        repo = snapshot.repo
        fetched = fmt.ago(snapshot.taken_at - repo.last_fetch) if repo.last_fetch else "never"
        behind = Text()
        if repo.behind:
            behind.append(f"{repo.behind} behind", style=theme.style("warn", bold=True))
        elif repo.behind == 0:
            behind.append("up to date", style=theme.style("good"))
        table.add_row("fetch", Text(fetched), behind)
        for problem in (snapshot.config_error, snapshot.docker_error, snapshot.exclusion_error):
            if problem:
                table.add_row("⚠", Text(problem, style=theme.style("bad")), "")
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
    def _pools(snapshot: MonitorSnapshot, theme: Theme) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        pools: dict[str, list[ProfileView]] = defaultdict(list)
        for view in snapshot.profiles:
            pools[view.status.provider].append(view)
        if not pools:
            table.add_row(Text("no Login Profiles enrolled", style=theme.style("muted")))
        for provider in sorted(pools):
            views = pools[provider]
            role = fmt.provider_role(provider)
            free = sum(1 for view in views if view.status.busy is False)
            table.add_row(
                Text(f"{provider.upper()} pool", style=theme.style(role, bold=True)),
                Text(f"{free}/{len(views)} untapped", style=theme.style("muted")),
                "",
            )
            for view in sorted(views, key=lambda item: item.status.slot):
                table.add_row(*StatusPane._profile(view, snapshot.taken_at, theme))
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
        live = sum(1 for view in runs if view.run.stage is not Stage.NEEDS_RECOVER)
        self.border_subtitle = f"{live} live on this host"
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
        if run.stage is Stage.NEEDS_RECOVER:
            candidate.stylize(theme.style("needs_recover"))
        candidate.append("\n" + "  ".join((*run.candidate.secondary, run.run_id[:8])), style=muted)
        progress = fmt.bar(view.budget_fraction(now), BAR_WIDTH, theme)
        if view.estimated_percent is not None:
            progress.append(
                f" ≈{view.estimated_percent:.0f}%", style=theme.style("accent", bold=True)
            )
        budget = fmt.short_duration(run.budget_seconds) if run.budget_seconds else fmt.DASH
        fraction = view.budget_fraction(now)
        used = f" · {fraction * 100:.0f}% of budget" if fraction is not None else ""
        progress.append(f"\n{fmt.short_duration(elapsed)} of {budget}{used}", style=muted)
        spend = fmt.money(view.cost, theme, provisional=True)
        if view.unpriced_requests:
            spend.append(f" +{view.unpriced_requests} unpriced", style=muted)
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
        text = Text()
        total = 0
        for batch in snapshot.queued:
            if batch.status in ("done",) and not batch.runs:
                continue
            text.append(
                f"{theme.glyph('batch')} {batch.batch}", style=theme.style("title", bold=True)
            )
            if batch.needs_ack:
                text.append(f"  {theme.glyph('needs_ack')}", style=theme.style("warn", bold=True))
            elif batch.not_before is not None and batch.not_before > snapshot.taken_at:
                text.append(
                    f"  {fmt.until(batch.not_before, snapshot.taken_at)}",
                    style=theme.style("accent"),
                )
            elif batch.error:
                text.append(f"  {batch.error}", style=theme.style("bad"))
            else:
                text.append(f"  {batch.status}", style=theme.style("muted"))
            text.append(f"  {batch.started}/{batch.total}\n", style=theme.style("muted"))
            for queued in batch.runs:
                total += 1
                text.append("  ")
                text.append_text(fmt.badge(queued.benchmark, theme))
                text.append(
                    f"  {fmt.short_duration(queued.budget_seconds)}\n", style=theme.style("muted")
                )
                text.append(f"    {queued.candidate.label}\n", style=theme.style("text"))
        if not text:
            text.append("nothing queued", style=theme.style("muted"))
        self.border_subtitle = f"{total} runs"
        self.query_one("#queue-body", Static).update(text)


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
