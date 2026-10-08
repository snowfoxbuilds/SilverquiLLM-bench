"""The dashboard: status, running runs and the queue, stacked across the full width."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import ClassVar

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.geometry import Region
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
COMPACT = 150
"""Below this many columns the status column narrows and running candidates are cut sooner."""
BAR_WIDTH = 12
SPARK_WIDTH = 16
CANDIDATE_WIDTH = 48
COMPACT_CANDIDATE_WIDTH = 34
COMPACT_PROGRESS_WIDTH = 24
COMPACT_SPARK_WIDTH = 12
WEEKLY_BAR = 10
POOLS = ("claude", "codex")
"""The Login Pools the LOGINS pane shows, left to right, one per login plugin."""
POOL_GAP = 3
FORMS = ((True, False), (False, False), (False, True))
"""The LOGINS pane's forms, fullest first, as (usage bars, short usage text)."""
MIN_NAME = 10
"""A profile name keeps at least this much when the pane is too narrow for all of it."""
QUEUED_BENCHMARK_WIDTH = 18


class RunChosen(Message):
    """The operator picked a run to open in run details."""

    def __init__(
        self, run_id: str, *, pinned: bool = False, record_path: str | None = None
    ) -> None:
        super().__init__()
        self.run_id = run_id
        self.pinned = pinned
        """Opened as one Run Record from history: details keep showing that record."""
        self.record_path = record_path
        """The pinned record's own path: several records can share one run id."""


class CooldownWanted(Message):
    """The operator pressed a cooldown key on a selected Login Profile."""

    def __init__(self, plugin_id: str, slot: str, *, lengthen: bool) -> None:
        super().__init__()
        self.plugin_id, self.slot = plugin_id, slot
        self.lengthen = lengthen
        """``t``: one more hour; otherwise ``c``: end the cooldown shortly."""


def _key(view: ProfileView) -> tuple[str, str]:
    return view.status.plugin_id, view.status.slot


def _short(path) -> str:
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home) :] if text.startswith(home) else text


def _shares(natural: list[int], least: list[int], room: int) -> list[int]:
    """Each pool column's width: its natural width and an even part of any room to spare,
    or, short of room, its natural width less a part of the names it can give up."""
    spare = room - sum(natural)
    if spare >= 0:
        return [width + spare // len(natural) for width in natural]
    give = [width - floor for width, floor in zip(natural, least, strict=True)]
    owed, total = -spare, sum(give) or 1
    cuts = [owed * part // total for part in give]
    cuts[-1] += owed - sum(cuts)
    return [width - cut for width, cut in zip(natural, cuts, strict=True)]


class StatusPane(Vertical):
    """One column: where the monitor reads from, then the run counts."""

    def __init__(self, theme: Theme) -> None:
        super().__init__(id="status", classes="pane")
        self.theme_ = theme
        self.border_title = "STATUS"

    def compose(self) -> ComposeResult:
        yield Static(id="where")
        yield Static(id="counts")

    def show(self, snapshot: MonitorSnapshot) -> None:
        theme = self.theme_
        self.set_class(self.app.size.width < COMPACT, "compact")
        self.query_one("#where", Static).update(self._where(snapshot, theme))
        self.query_one("#counts", Static).update(self._counts(snapshot, theme))

    @staticmethod
    def _where(snapshot: MonitorSnapshot, theme: Theme) -> Table:
        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column(style=theme.style("muted"), no_wrap=True, min_width=7)
        table.add_column(overflow="ellipsis", no_wrap=True, ratio=1)
        table.add_column(no_wrap=True)
        muted = theme.style("muted")
        for key, label in LOCATION_LABELS.items():
            location = snapshot.locations.get(key)
            if location is None or location.path is None:
                table.add_row(label, Text("unset", style=theme.style("bad", bold=True)), "")
            else:
                # The source keeps its own column, so a long path is the part cut short.
                source = Text(f"({location.source})", style=muted)
                table.add_row(label, Text(_short(location.path)), source)
        repo = snapshot.repo
        fetched = Text(fmt.ago(snapshot.taken_at - repo.last_fetch) if repo.last_fetch else "never")
        if repo.behind:
            fetched.append(f" · {repo.behind} behind", style=theme.style("warn", bold=True))
        elif repo.behind == 0:
            fetched.append(" · up to date", style=theme.style("good"))
        table.add_row("fetch", fetched, "")
        table.add_row("host", Text(snapshot.host_label or "unlabelled", style=muted), "")
        for problem in (snapshot.config_error, snapshot.docker_error, snapshot.exclusion_error):
            if problem:
                table.add_row(
                    Text(theme.glyph("problem")), Text(problem, style=theme.style("bad")), ""
                )
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


class LoginsPane(VerticalScroll, can_focus=False):
    """Every Login Pool side by side: each profile busy, free or held, with its usage.

    The pools sit in columns while both fit, usage bars included when there is room, and
    stack when they do not; more profiles than the pane's height scroll.
    """

    def __init__(self, theme: Theme) -> None:
        super().__init__(id="logins", classes="pane")
        self.theme_ = theme
        self.border_title = "LOGINS"
        self.snapshot: MonitorSnapshot | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="pool-row"):
            for provider in POOLS:
                yield PoolPanel(self.theme_, provider)

    def show(self, snapshot: MonitorSnapshot) -> None:
        self.snapshot = snapshot
        self._arrange()

    def on_resize(self) -> None:
        self._arrange()

    def _arrange(self) -> None:
        """Columns while both pools fit, fullest form first; otherwise stacked, scrolling."""
        snapshot = self.snapshot
        if snapshot is None:
            return
        panels = list(self.query(PoolPanel))
        width = self.content_size.width
        gaps = POOL_GAP * (len(panels) - 1)
        row = self.query_one("#pool-row")
        # A form that fits whole beats one that fits only by cutting profile names.
        tries = [(form, "natural_width") for form in FORMS] + [
            (form, "least_width") for form in FORMS
        ]
        for (bars, short), measure in tries:
            natural = [panel.natural_width(snapshot, bars=bars, short=short) for panel in panels]
            least = [panel.least_width(snapshot, bars=bars, short=short) for panel in panels]
            needed = natural if measure == "natural_width" else least
            if not width or sum(needed) + gaps <= width:
                row.remove_class("stacked")
                shares = _shares(natural, least, width - gaps) if width else natural
                for panel, share in zip(panels, shares, strict=True):
                    panel.styles.width = share
                    panel.show(snapshot, bars=bars, short=short)
                return
        row.add_class("stacked")
        bars, short = next((form for form in FORMS if self._fits(panels, form, width)), FORMS[-1])
        for panel in panels:
            panel.styles.width = "1fr"
            panel.show(snapshot, bars=bars, short=short)

    def _fits(self, panels: list[PoolPanel], form: tuple[bool, bool], width: int) -> bool:
        bars, short = form
        return all(
            panel.least_width(self.snapshot, bars=bars, short=short) <= width for panel in panels
        )

    @staticmethod
    def views(snapshot: MonitorSnapshot, provider: str) -> list[ProfileView]:
        """One pool's profiles in drawing order."""
        views = [view for view in snapshot.profiles if view.status.provider == provider]
        return sorted(views, key=lambda view: view.status.slot)

    @staticmethod
    def pool(
        snapshot: MonitorSnapshot,
        provider: str,
        theme: Theme,
        *,
        bars: bool = True,
        short: bool = False,
        selected: tuple[str, str] | None = None,
        width: int | None = None,
    ) -> Table:
        """A pool's header and untapped count, then one line per profile.

        Given the column's ``width``, a profile's name is cut before its usage figures are.
        """
        views = LoginsPane.views(snapshot, provider)
        role = fmt.provider_role(provider)
        # Untapped means a new run could take it now: not busy, pending or cooling down.
        free = sum(1 for view in views if view.status.free)
        title = Text(f"{provider.upper()} pool", style=theme.style(role, bold=True))
        untapped = Text(f"{free}/{len(views)} untapped", style=theme.style("muted"))
        rows: list[tuple[tuple[Text, ...], str | None]] = [((title, Text(), untapped), None)]
        for view in views:
            cells = LoginsPane.profile(view, snapshot.taken_at, theme, short=short)
            rows.append((cells, theme.selected() if _key(view) == selected else None))
        if not views:
            rows.append(((Text("none enrolled", style=theme.style("muted")), Text(), Text()), None))
        name_width = max(cells[0].cell_len for cells, _ in rows)
        usage_width = max(cells[2].cell_len for cells, _ in rows)
        bar_width = WEEKLY_BAR if bars else 0
        if width:
            room = max(0, width - bar_width - (2 if bars else 1))
            usage_width = min(usage_width, max(0, room - MIN_NAME))
            name_width = max(min(name_width, room - usage_width), min(MIN_NAME, room))
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True, overflow="ellipsis", width=name_width or None)
        if bars:
            table.add_column(no_wrap=True, width=bar_width)
        table.add_column(no_wrap=True, overflow="ellipsis", width=usage_width or None)
        for (name, bar, weekly), mark in rows:
            table.add_row(*((name, bar, weekly) if bars else (name, weekly)), style=mark)
        return table

    @staticmethod
    def profile(view: ProfileView, now: datetime, theme: Theme, *, short: bool = False) -> tuple:
        """A profile's name with its state glyph, its usage bar, and its usage text."""
        status = view.status
        if status.pending:
            mark = Text(theme.glyph("pending"), style=theme.style("bad", bold=True))
        elif status.cooldown_until is not None and not status.busy:
            mark = Text(theme.glyph("cooldown"), style=theme.style("cooldown", bold=True))
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
        weekly = fmt.weekly(view.weekly, now, theme, short=short)
        if status.cooldown_until is not None:
            # A held profile reads its hold first: when it ends matters more than its usage,
            # which a short form leaves out.
            held = fmt.cooldown(status.cooldown_until, now, theme, short=short)
            if not short:
                held.append(theme.glyph("sep"), style=theme.style("muted"))
                held.append_text(weekly)
            weekly = held
        if status.pending_run:
            # The run that still owns this login's settlement; recovering it frees the profile.
            owner = Text(
                f"{theme.glyph('pending')} {status.pending_run[:8]}", style=theme.style("bad")
            )
            owner.append(theme.glyph("sep"), style=theme.style("muted"))
            owner.append_text(weekly)
            weekly = owner
        return name, fmt.bar(percent, WEEKLY_BAR, theme), weekly


class PoolPanel(Static, can_focus=True):
    """One Login Pool, one selectable line per profile: ``t`` and ``c`` set Login Cooldowns."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up,k", "move(-1)", "Previous profile", show=False),
        Binding("down,j", "move(1)", "Next profile", show=False),
        Binding("left,h", "app.focus_previous", "Previous pane", show=False),
        Binding("right,l", "app.focus_next", "Next pane", show=False),
        Binding("t", "cooldown(True)", "Cooldown +1h", show=False),
        Binding("c", "cooldown(False)", "End cooldown", show=False),
    ]

    def __init__(self, theme: Theme, provider: str) -> None:
        super().__init__(id=f"pool-{provider}", classes="pool")
        self.theme_ = theme
        self.provider = provider
        self.snapshot: MonitorSnapshot | None = None
        self.bars = True
        self.short = False
        self.selected: tuple[str, str] | None = None
        """The selected profile by identity, so a refresh keeps it selected."""

    def natural_width(self, snapshot: MonitorSnapshot, *, bars: bool, short: bool) -> int:
        """The column's width with nothing cut."""
        table = LoginsPane.pool(snapshot, self.provider, self.theme_, bars=bars, short=short)
        return sum(column.width or 0 for column in table.columns) + len(table.columns) - 1

    def least_width(self, snapshot: MonitorSnapshot, *, bars: bool, short: bool) -> int:
        """The narrowest the column reads in: only profile names are cut, to ``MIN_NAME``."""
        table = LoginsPane.pool(snapshot, self.provider, self.theme_, bars=bars, short=short)
        names = table.columns[0].width or 0
        return self.natural_width(snapshot, bars=bars, short=short) - max(0, names - MIN_NAME)

    def show(self, snapshot: MonitorSnapshot, *, bars: bool = True, short: bool = False) -> None:
        self.snapshot, self.bars, self.short = snapshot, bars, short
        if self.selected not in self._keys():
            self.selected = None
        self._draw()

    def _keys(self) -> list[tuple[str, str]]:
        if self.snapshot is None:
            return []
        return [_key(view) for view in LoginsPane.views(self.snapshot, self.provider)]

    def _draw(self) -> None:
        if self.snapshot is None:
            return
        # Only a focused pool shows its selection, so an unfocused dashboard reads as before.
        selected = self.selected if self.has_focus else None
        self.update(
            LoginsPane.pool(
                self.snapshot,
                self.provider,
                self.theme_,
                bars=self.bars,
                short=self.short,
                selected=selected,
                width=self.content_size.width or None,
            )
        )
        if selected is not None:
            self._keep_visible(self._keys().index(selected) + 1)

    def _keep_visible(self, line: int) -> None:
        """Scroll the LOGINS pane so the selected line stays in view."""
        pane = next((node for node in self.ancestors if isinstance(node, LoginsPane)), None)
        if pane is None or not self.region.height:
            return
        top = self.region.y - pane.content_region.y + round(pane.scroll_y) + line
        pane.scroll_to_region(Region(0, top, 1, 1), animate=False, immediate=True)

    def on_resize(self) -> None:
        self._draw()

    def on_focus(self) -> None:
        if self.selected is None and self._keys():
            self.selected = self._keys()[0]
        self._draw()

    def on_blur(self) -> None:
        self._draw()

    def action_move(self, step: int) -> None:
        keys = self._keys()
        if not keys:
            return
        index = keys.index(self.selected) + step if self.selected in keys else 0
        self.selected = keys[max(0, min(index, len(keys) - 1))]
        self._draw()

    def action_cooldown(self, lengthen: bool) -> None:
        if self.selected is not None:
            self.post_message(CooldownWanted(*self.selected, lengthen=lengthen))

    def on_click(self, event: Click) -> None:
        offset = event.get_content_offset(self)
        keys = self._keys()
        # The pool's header is the first line, so profile n sits on line n + 1.
        if offset is not None and 1 <= offset.y <= len(keys):
            self.selected = keys[offset.y - 1]
            self.focus()
            self._draw()


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
        compact = self.app.size.width < COMPACT
        width = COMPACT_CANDIDATE_WIDTH if compact else CANDIDATE_WIDTH
        for view in runs:
            cells = self._cells(view, now, theme, candidate_width=width, compact=compact)
            table.add_row(*cells, key=view.run.run_id, height=2)
            self._order.append(view.run.run_id)
        if selected in self._order:
            table.move_cursor(row=self._order.index(selected), animate=False)

    @staticmethod
    def _cells(
        view: RunView,
        now: datetime,
        theme: Theme,
        *,
        candidate_width: int = CANDIDATE_WIDTH,
        compact: bool = False,
    ) -> tuple:
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
        candidate.truncate(candidate_width, overflow="ellipsis")
        if run.stage is Stage.NEEDS_RECOVER:
            candidate.stylize(theme.style("needs_recover"))
        labels = Text("  ".join((*run.candidate.secondary, run.run_id[:8])), style=muted)
        labels.truncate(candidate_width, overflow="ellipsis")
        candidate.append("\n")
        candidate.append_text(labels)
        if run.stage in (Stage.NEEDS_RECOVER, Stage.UNKNOWN):
            # Its progress no longer matters; why it is stuck, and whether it still runs, does.
            progress = fmt.reasons(run, theme)
            progress.truncate(
                COMPACT_PROGRESS_WIDTH if compact else candidate_width, overflow="ellipsis"
            )
        else:
            progress = fmt.progress(view.estimated_percent, BAR_WIDTH, theme)
        progress.append("\n")
        progress.append_text(fmt.elapsed_of_budget(elapsed, run.budget_seconds, theme))
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
        spark = COMPACT_SPARK_WIDTH if compact else SPARK_WIDTH
        spend.append_text(fmt.sparkline(view.request_costs, spark, theme, until_ms=stamp))
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
            state = Text(
                f"{theme.glyph('batch')} {batch.batch}  ", style=theme.style("title", bold=True)
            )
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
                run.pad_right(max(0, QUEUED_BENCHMARK_WIDTH - run.cell_len))
                run.append(f"{fmt.short_duration(queued.budget_seconds):>4}  ", style=muted)
                run.append(queued.candidate.label, style=theme.style("text"))
                lines.append(run)
        if not lines:
            lines.append(Text("nothing queued", style=muted))
        self.border_subtitle = f"{total} runs"
        # One line per entry: a long candidate is cut at the pane's edge rather than wrapped,
        # at whatever width the pane has when drawn.
        body = Text("\n").join(lines)
        body.no_wrap, body.overflow = True, "ellipsis"
        self.query_one("#queue-body", Static).update(body)


class DashboardView(Vertical):
    """Status and logins side by side on top, then running runs and the queue, full width."""

    def __init__(self, theme: Theme) -> None:
        super().__init__(id="dashboard")
        self.theme_ = theme

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-row"):
            yield StatusPane(self.theme_)
            yield LoginsPane(self.theme_)
        yield RunningPane(self.theme_)
        yield QueuedPane(self.theme_)

    def show(self, snapshot: MonitorSnapshot) -> None:
        self.query_one(StatusPane).show(snapshot)
        self.query_one(LoginsPane).show(snapshot)
        self.query_one(RunningPane).show(snapshot)
        self.query_one(QueuedPane).show(snapshot)
