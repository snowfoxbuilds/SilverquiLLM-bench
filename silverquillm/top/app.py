"""The Textual application: three views over one ``Monitor``, polled off the UI thread."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.markup import escape
from textual.message import Message
from textual.timer import Timer
from textual.widgets import ContentSwitcher, Static
from textual.worker import Worker, WorkerState

from silverquillm.monitor import LogLine, Monitor, MonitorSnapshot, RunSummary

from .dashboard import NARROW, DashboardView, RunChosen
from .details import DetailsView
from .historic import HistoryView
from .theme import Theme

VIEWS = (("dashboard", "1", "Dashboard"), ("history", "2", "History"), ("details", "3", "Run"))


@dataclass(frozen=True)
class Fetch:
    """One details request, tied to the details generation it was made for."""

    generation: int
    run_id: str
    live: bool
    since: int
    logs: bool
    summary: RunSummary | None


class Polled(Message):
    def __init__(self, snapshot: MonitorSnapshot, runs: list[RunSummary]) -> None:
        super().__init__()
        self.snapshot, self.runs = snapshot, runs


class Fetched(Message):
    def __init__(self, request: Fetch, lines: list[LogLine], requests, workspace, detail) -> None:
        super().__init__()
        self.request, self.lines, self.requests = request, lines, requests
        self.workspace, self.detail = workspace, detail


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
        # Serialises monitor calls between the poll and details workers.
        self._lock = threading.Lock()
        # Guards only the in-flight count; nothing holds it during I/O.
        self._state = threading.Lock()
        self._inflight = 0
        self._shutting_down = self._close_wanted = self._monitor_closed = False
        self._polling = self._poll_again = False
        self._fetching = self._fetch_again = False
        self._timer: Timer | None = None
        self._details: DetailsView | None = None
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
        self._details = self.query_one(DetailsView)
        self._draw_bars()
        self.poll()
        self._timer = self.set_interval(self.interval, self.poll)

    def on_resize(self, event: events.Resize) -> None:
        # Below this width the queue moves under the running runs so their rows fit.
        self.query_one(DashboardView).set_class(event.size.width < NARROW, "narrow")

    def on_unmount(self) -> None:
        self.release_monitor()

    async def action_quit(self) -> None:
        self._stop_scheduling()
        self.exit()

    # Background work -------------------------------------------------------
    #
    # A thread cannot be cancelled, so each kind of work has at most one thread in flight and
    # at most one coalesced request waiting behind it: a slow Docker daemon then delays the
    # view instead of piling up threads. Scheduling flags change only on the UI thread.

    def _stop_scheduling(self) -> None:
        self._shutting_down = True
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def release_monitor(self) -> None:
        """Close the monitor once no worker can use it, without waiting on a worker.

        With work in flight, the last worker to finish closes it instead.
        """
        self._stop_scheduling()
        with self._state:
            self._close_wanted = True
            close = self._inflight == 0 and not self._monitor_closed
            self._monitor_closed = self._monitor_closed or close
        if close:
            self.monitor.close()

    def _start(self, work: Callable[[], Message | None], group: str) -> None:
        with self._state:
            self._inflight += 1
        self.run_worker(
            lambda: self._guarded(work), group=group, thread=True, exit_on_error=False
        )

    def _guarded(self, work: Callable[[], Message | None]) -> None:
        try:
            result = None if self._shutting_down else work()
            if result is not None and not self._shutting_down:
                try:
                    self.post_message(result)
                except RuntimeError:
                    pass  # the app's event loop has already closed
        finally:
            with self._state:
                self._inflight -= 1
                close = self._close_wanted and self._inflight == 0 and not self._monitor_closed
                self._monitor_closed = self._monitor_closed or close
            if close:
                self.monitor.close()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        # A worker that raised posts nothing; free its slot so scheduling continues.
        if event.state is WorkerState.ERROR:
            if event.worker.group == "poll":
                self._polling = False
                self._resume_poll()
            elif event.worker.group == "details":
                self._fetching = False
                self._resume_fetch()

    def poll(self) -> None:
        """Ask for a fresh snapshot; a request while one is in flight runs after it, once."""
        if self._shutting_down:
            return
        if self._polling:
            self._poll_again = True
            return
        self._polling = True
        self._start(self._read_snapshot, "poll")

    def _read_snapshot(self) -> Polled | None:
        with self._lock:
            if self._shutting_down:
                return None
            snapshot = self.monitor.snapshot()
            runs = self.monitor.history()
        return Polled(snapshot, runs)

    def on_polled(self, message: Polled) -> None:
        self._polling = False
        if self._shutting_down:
            return
        self._apply(message.snapshot, message.runs)
        self._resume_poll()

    def _resume_poll(self) -> None:
        if self._poll_again:
            self._poll_again = False
            self.poll()

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
        self.fetch_details()

    def fetch_details(self) -> None:
        """Fetch what the shown run still lacks; at most one fetch is in flight."""
        details = self.query_one(DetailsView)
        shown = details.shown
        if shown is None or self._shutting_down:
            return
        if self._fetching:
            self._fetch_again = True
            return
        live = shown.live is not None
        want_logs = live or not shown.retained_loaded
        # A recorded run's detail is retried until it reads: its summary can reach the
        # history after the run leaves the live view, and a manifest can be briefly unreadable.
        want_detail = not live and not shown.detail_ready and shown.summary is not None
        if not (want_logs or want_detail):
            return
        request = Fetch(
            details.generation,
            shown.run_id,
            live,
            shown.seq if live else 0,
            want_logs,
            shown.summary if want_detail else None,
        )
        self._fetching = True
        self._start(lambda: self._read_details(request), "details")

    def _read_details(self, request: Fetch) -> Fetched | None:
        with self._lock:
            if self._shutting_down or self._stale(request):
                return None
            lines: list[LogLine] = []
            requests: list = []
            workspace = detail = None
            if request.logs:
                lines = self.monitor.output(request.run_id, since=request.since)
                workspace = self.monitor.workspace(request.run_id)
            if request.live:
                requests = list(self.monitor.provisional_requests(request.run_id))
            if request.summary is not None:
                try:
                    detail = self.monitor.record_detail(request.summary)
                except Exception:  # noqa: BLE001 - an unreadable record is retried, not fatal
                    detail = None
        return Fetched(request, lines, requests, workspace, detail)

    def _stale(self, request: Fetch) -> bool:
        details = self._details
        return details is None or details.generation != request.generation

    def on_fetched(self, message: Fetched) -> None:
        self._fetching = False
        if self._shutting_down:
            return
        details = self.query_one(DetailsView)
        shown, request = details.shown, message.request
        if (
            shown is not None
            and not self._stale(request)
            and (shown.live is not None) == request.live
        ):
            self._show_details(details, message)
        self._resume_fetch()

    def _resume_fetch(self) -> None:
        if self._fetch_again:
            self._fetch_again = False
            self.fetch_details()

    def _show_details(self, details: DetailsView, message: Fetched) -> None:
        shown, request = details.shown, message.request
        if request.logs and (request.live or not shown.retained_loaded):
            details.append_output(message.lines)
            shown.retained_loaded = not request.live
        if message.workspace is not None:
            details.show_workspace(message.workspace)
        if request.live:
            details.show_requests(message.requests, self.clock())
        elif message.detail is not None:
            shown.detail, shown.detail_ready = message.detail, True
            details.show_requests(message.detail.requests, self.clock())
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
