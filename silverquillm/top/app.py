"""The Textual application: three views over one ``Monitor``, polled off the UI thread."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import ClassVar

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.markup import escape
from textual.widgets import ContentSwitcher, Static

from silverquillm.monitor import Monitor, MonitorSnapshot, RunSummary

from .dashboard import NARROW, DashboardView, RunChosen
from .details import DetailsView
from .historic import HistoryView
from .theme import Theme

VIEWS = (("dashboard", "1", "Dashboard"), ("history", "2", "History"), ("details", "3", "Run"))


def _tag(style: str, text: str) -> str:
    return f"[{style}]{text}[/]" if style and style != "none" else text


class MonitorApp(App):
    """Read-only: every monitor call runs in a worker, and nothing here writes or locks."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "silverquillm top"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("1", "view('dashboard')", "Dashboard", show=False),
        Binding("2", "view('history')", "History", show=False),
        Binding("3", "view('details')", "Run", show=False),
        Binding("escape", "back", "Back", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        monitor: Monitor,
        look: Theme,
        *,
        interval: float = 2.0,
        notice: str | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(ansi_color=look.name == "plain")
        self.monitor = monitor
        self.look = look
        self.interval = interval
        self.notice = notice
        self.clock = clock
        self.snapshot: MonitorSnapshot | None = None
        self.runs: list[RunSummary] = []
        self._lock = threading.Lock()
        self._previous = "dashboard"
        self._current = "dashboard"

    def compose(self) -> ComposeResult:
        yield Static(id="topbar")
        with ContentSwitcher(initial="dashboard", id="switcher"):
            yield DashboardView(self.look)
            yield HistoryView(self.look)
            yield DetailsView(self.look)
        yield Static(id="keys")

    def on_mount(self) -> None:
        self._draw_bars()
        self.poll()
        self.set_interval(self.interval, self.poll)

    def on_resize(self, event: events.Resize) -> None:
        # Below this width the queue moves under the running runs so their rows fit.
        self.query_one(DashboardView).set_class(event.size.width < NARROW, "narrow")

    def on_unmount(self) -> None:
        with self._lock:
            self.monitor.close()

    # Polling ---------------------------------------------------------------

    @work(thread=True, exclusive=True, group="poll")
    def poll(self) -> None:
        with self._lock:
            snapshot = self.monitor.snapshot()
            runs = self.monitor.history()
        self.call_from_thread(self._apply, snapshot, runs)

    def _apply(self, snapshot: MonitorSnapshot, runs: list[RunSummary]) -> None:
        self.snapshot, self.runs = snapshot, runs
        self.query_one(DashboardView).show(snapshot)
        self.query_one(HistoryView).show(runs)
        self._refresh_details()
        self._draw_bars()

    def _refresh_details(self) -> None:
        details = self.query_one(DetailsView)
        shown = details.shown
        if shown is None or self.snapshot is None:
            return
        was_live = shown.live is not None
        shown.live = next(
            (view for view in self.snapshot.running if view.run.run_id == shown.run_id), None
        )
        shown.summary = next((run for run in self.runs if run.run_id == shown.run_id), None)
        if was_live and shown.live is None:
            details.restart_output()
        details.show_header(self.snapshot.taken_at)
        if shown.live is not None or not shown.loaded_retained:
            self.fetch_details(shown.run_id, shown.seq, shown.live is not None, shown.summary)

    @work(thread=True, exclusive=True, group="details")
    def fetch_details(
        self, run_id: str, since: int, live: bool, summary: RunSummary | None
    ) -> None:
        with self._lock:
            if live:
                lines = self.monitor.output(run_id, since=since)
                requests = list(self.monitor.provisional_requests(run_id))
                detail = None
            else:
                lines = self.monitor.output(run_id, since=0)
                detail = self.monitor.record_detail(summary) if summary else None
                requests = detail.requests if detail else []
            workspace = self.monitor.workspace(run_id)
        self.call_from_thread(self._apply_details, run_id, live, lines, requests, workspace, detail)

    def _apply_details(self, run_id, live, lines, requests, workspace, detail) -> None:
        details = self.query_one(DetailsView)
        shown = details.shown
        if shown is None or shown.run_id != run_id or (shown.live is not None) != live:
            return
        if not live:
            if shown.loaded_retained:
                return
            shown.loaded_retained = True
            shown.detail = detail
        details.append_output(lines)
        details.show_requests(requests, self.clock())
        details.show_workspace(workspace)
        details.show_header(self.clock())

    # Views -----------------------------------------------------------------

    def _draw_bars(self) -> None:
        look = self.look
        title, muted = look.style("title", bold=True), look.style("muted")
        parts = [_tag(title, f" {look.glyph('logo')} "), " ", _tag(muted, "top"), "  "]
        for name, key, label in VIEWS:
            style = f"{title} reverse" if name == self._current else muted
            parts.append(f"[@click=app.view('{name}')]{_tag(style, f' {key} {label} ')}[/] ")
        snapshot = self.snapshot
        clock = (snapshot.taken_at if snapshot else self.clock()).astimezone().strftime("%H:%M:%S")
        parts.append("  " + _tag(muted, f"refresh {self.interval:g}s · {clock}"))
        if self.notice:
            parts.append("  " + _tag(look.style("warn"), escape(self.notice)))
        self.query_one("#topbar", Static).update("".join(parts))
        hints = {
            "dashboard": "enter/click open run",
            "history": "enter/click open run · click header or s sort · S reverse · x excluded",
            "details": "esc back · tabs: click or ←/→",
        }[self._current]
        keys = _tag(muted, f" 1/2/3 views · {hints} · r refresh · ")
        self.query_one("#keys", Static).update(
            keys + f"[@click=app.quit]{_tag(muted, 'q quit')}[/]"
        )

    def action_view(self, name: str) -> None:
        if name == self._current:
            return
        self._previous, self._current = self._current, name
        self.query_one("#switcher", ContentSwitcher).current = name
        self._draw_bars()
        focus = {"dashboard": "#running-table", "history": "#runs-table"}.get(name)
        if focus:
            self.query_one(focus).focus()

    def action_back(self) -> None:
        if self._current == "details":
            self.action_view(self._previous if self._previous != "details" else "dashboard")

    def action_refresh(self) -> None:
        self.poll()

    def on_run_chosen(self, message: RunChosen) -> None:
        details = self.query_one(DetailsView)
        details.open(message.run_id)
        self.action_view("details")
        self._refresh_details()


def build_app(monitor: Monitor, look: Theme, **options) -> MonitorApp:
    """The app with the theme's stylesheet; the theme decides every colour and border."""
    themed = type("ThemedMonitorApp", (MonitorApp,), {"CSS": look.css()})
    return themed(monitor, look, **options)
