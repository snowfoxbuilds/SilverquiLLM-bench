"""The Textual application: three views over one ``Monitor``, polled off the UI thread."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.markup import escape
from textual.message import Message
from textual.timer import Timer
from textual.widgets import ContentSwitcher, Static

from silverquillm.monitor import LogLine, Monitor, MonitorSnapshot, RunSummary, WorkspaceView

from .dashboard import DashboardView, RunChosen
from .details import DetailsView
from .historic import HistoryView
from .keys import HelpScreen
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
    """The applicable record whose detail to read, or None when none is wanted."""
    record_key: tuple[str, str] | None
    provisional: bool
    """No record applies to this live run yet, so its requests come from telemetry."""
    record_hash: str | None = None
    """A pinned record's Candidate Hash: this host's logs and workspace are shown only when
    its run directory was launched for that candidate, since run ids can repeat."""


@dataclass(frozen=True)
class Polled:
    snapshot: MonitorSnapshot
    runs: list[RunSummary]


@dataclass(frozen=True)
class Fetched:
    request: Fetch
    lines: list[LogLine]
    requests: list
    workspace: object
    detail: object


class JobDone(Message):
    """Every started job posts exactly one of these, whether it read, skipped or failed."""

    def __init__(self, kind: str, job: int, result: Polled | Fetched | None) -> None:
        super().__init__()
        self.kind, self.job, self.result = kind, job, result


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
        Binding("question_mark", "help", "Keys", show=False),
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
        driver_class=None,
    ) -> None:
        super().__init__(driver_class=driver_class, ansi_color=look.name == "plain")
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
        # Per kind of job: the one in flight (by id) and whether another is wanted after it.
        self._job_ids = itertools.count(1)
        self._active: dict[str, int | None] = {"poll": None, "details": None}
        self._again: dict[str, bool] = {"poll": False, "details": False}
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

    def on_unmount(self) -> None:
        self.release_monitor()

    async def action_quit(self) -> None:
        self._stop_scheduling()
        self.exit()

    @property
    def busy(self) -> dict[str, bool]:
        """Which kinds of job have one in flight; for tests and the curious."""
        return {kind: job is not None for kind, job in self._active.items()}

    # Background work -------------------------------------------------------
    #
    # A thread cannot be cancelled, so each kind of work has at most one thread in flight and
    # at most one coalesced request waiting behind it: a slow Docker daemon then delays the
    # view instead of piling up threads. The threads are the app's own daemon threads, not
    # asyncio's default executor, whose teardown would make quitting wait for a stuck read.
    # Scheduling state changes only on the UI thread, when a job's ``JobDone`` arrives.

    def _stop_scheduling(self) -> None:
        if not self._shutting_down:
            self._shutting_down = True
            # Followers' ``docker logs`` exit now; nothing here waits for them.
            self.monitor.begin_shutdown()
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def release_monitor(self) -> None:
        """Close the monitor once no job can use it, without waiting on a job.

        With a job in flight, the last job to finish closes it on its own thread instead.
        """
        self._stop_scheduling()
        with self._state:
            self._close_wanted = True
            close = self._inflight == 0 and not self._monitor_closed
            self._monitor_closed = self._monitor_closed or close
        if close:
            self.monitor.close()

    def _start(self, kind: str, work: Callable[[], Polled | Fetched | None]) -> None:
        job = next(self._job_ids)
        self._active[kind] = job
        with self._state:
            self._inflight += 1
        thread = threading.Thread(
            target=self._run, args=(kind, job, work), name=f"top-{kind}-{job}", daemon=True
        )
        try:
            thread.start()
        except RuntimeError:  # no thread to be had: the slot frees and the next tick retries
            self._finish()
            self._active[kind] = None

    def _run(self, kind: str, job: int, work: Callable[[], Polled | Fetched | None]) -> None:
        result = None
        try:
            if not self._shutting_down:
                result = work()
        except Exception:  # noqa: BLE001 - a failed read frees its slot like any other
            result = None
        finally:
            try:
                self.post_message(JobDone(kind, job, result))
            except RuntimeError:
                pass  # the app's event loop has already closed
            self._finish()

    def _finish(self) -> None:
        with self._state:
            self._inflight -= 1
            close = self._close_wanted and self._inflight == 0 and not self._monitor_closed
            self._monitor_closed = self._monitor_closed or close
        if close:
            self.monitor.close()

    def on_job_done(self, message: JobDone) -> None:
        if self._active.get(message.kind) != message.job:
            return  # an old job's completion never frees a newer job's slot
        self._active[message.kind] = None
        if self._shutting_down:
            return
        result = message.result
        if isinstance(result, Polled):
            self._apply(result.snapshot, result.runs)
        elif isinstance(result, Fetched):
            self._fetched(result)
        self._resume(message.kind)

    def _resume(self, kind: str) -> None:
        if self._again[kind]:
            self._again[kind] = False
            self.poll() if kind == "poll" else self.fetch_details()

    def poll(self) -> None:
        """Ask for a fresh snapshot; a request while one is in flight runs after it, once."""
        if self._shutting_down:
            return
        if self._active["poll"] is not None:
            self._again["poll"] = True
            return
        self._start("poll", self._read_snapshot)

    def _read_snapshot(self) -> Polled | None:
        with self._lock:
            if self._shutting_down:
                return None
            snapshot = self.monitor.snapshot()
            runs = self.monitor.history()
        return Polled(snapshot, runs)

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
        summary = self._applicable(shown)
        if (
            shown.pinned
            and shown.live is not None
            and summary is not None
            and shown.live.run.candidate_hash not in (None, summary.candidate_hash)
        ):
            # Same run id, another candidate's execution: none of it belongs to this record.
            shown.live = None
        key = (summary.run_id, str(summary.path)) if summary is not None else None
        shown.summary = summary
        if key != shown.record_key:
            # Another record now applies, as when a linked recovery replaces the original:
            # whatever the old record supplied is obsolete, and a fetch for it is ignored.
            shown.record_key, shown.detail, shown.detail_ready = key, None, False
            shown.requests = []
            details.clear_requests()
        if was_live and shown.live is None:
            details.restart_output()
        details.show_header(self.snapshot.taken_at)
        self.fetch_details()

    def _applicable(self, shown) -> RunSummary | None:
        """The one Run Record the details view takes its record facts from.

        A record opened from history stays exactly that record, found by its path. Any other
        execution follows the record the monitor applies to it this pass, live or Finished, so a
        recovery that finishes between two polls still replaces its original. The last applied
        record is only a fallback for a pass that could not read one.
        """

        def history(run_id: str, candidate_hash: str | None = None) -> RunSummary | None:
            return next(
                (
                    run
                    for run in self.runs
                    if run.run_id == run_id
                    and (candidate_hash is None or run.candidate_hash == candidate_hash)
                ),
                None,
            )

        if shown.pinned:
            if shown.record_path is not None:
                return next((run for run in self.runs if str(run.path) == shown.record_path), None)
            return history(shown.run_id)
        if shown.live is not None:
            record = shown.live.run.record
            if record is not None:
                shown.last_record = record
            return record
        current = self.snapshot.records.get(shown.run_id) if self.snapshot else None
        if current is not None:
            shown.last_record = current
            return current
        if shown.last_record is not None:
            last = shown.last_record
            return history(last.run_id, last.candidate_hash) or last
        return history(shown.run_id)

    def fetch_details(self) -> None:
        """Fetch what the shown run still lacks; at most one fetch is in flight."""
        details = self.query_one(DetailsView)
        shown = details.shown
        if shown is None or self._shutting_down:
            return
        if self._active["details"] is not None:
            self._again["details"] = True
            return
        live = shown.live is not None
        want_logs = live or not shown.retained_loaded
        # The applicable record's detail is retried until it reads, live or not: its summary
        # can arrive late, and a record file can be briefly unreadable.
        want_detail = not shown.detail_ready and shown.summary is not None
        provisional = live and shown.summary is None
        if not (want_logs or want_detail or provisional):
            return
        request = Fetch(
            details.generation,
            shown.run_id,
            live,
            shown.seq if live else 0,
            want_logs,
            shown.summary if want_detail else None,
            shown.record_key,
            provisional,
            shown.summary.candidate_hash if shown.pinned and shown.summary is not None else None,
        )
        self._start("details", lambda: self._read_details(request))

    def _read_details(self, request: Fetch) -> Fetched | None:
        with self._lock:
            if self._shutting_down or self._stale(request):
                return None
            lines: list[LogLine] = []
            requests: list = []
            workspace = detail = None
            if request.logs and not self._foreign(request):
                lines = self.monitor.output(request.run_id, since=request.since)
                workspace = self.monitor.workspace(request.run_id)
            elif request.logs:
                workspace = WorkspaceView([], [])
            if request.provisional:
                requests = list(self.monitor.provisional_requests(request.run_id))
            if request.summary is not None:
                try:
                    detail = self.monitor.record_detail(request.summary)
                except Exception:  # noqa: BLE001 - an unreadable record is retried, not fatal
                    detail = None
        return Fetched(request, lines, requests, workspace, detail)

    def _foreign(self, request: Fetch) -> bool:
        """This host's run directory under the run id belongs to another candidate's record."""
        if request.live or request.record_hash is None:
            return False
        return self.monitor.local_candidate_hash(request.run_id) != request.record_hash

    def _stale(self, request: Fetch) -> bool:
        details = self._details
        return details is None or details.generation != request.generation

    def _fetched(self, message: Fetched) -> None:
        details = self.query_one(DetailsView)
        shown, request = details.shown, message.request
        if (
            shown is not None
            and not self._stale(request)
            and (shown.live is not None) == request.live
        ):
            self._show_details(details, message)

    def _show_details(self, details: DetailsView, message: Fetched) -> None:
        shown, request = details.shown, message.request
        if request.logs and (request.live or not shown.retained_loaded):
            details.append_output(message.lines)
            shown.retained_loaded = not request.live
        if message.workspace is not None:
            details.show_workspace(message.workspace)
        if request.summary is not None:
            if request.record_key == shown.record_key:  # else another record applies by now
                if message.detail is not None:
                    shown.detail, shown.detail_ready = message.detail, True
                    details.show_requests(message.detail.requests, self.clock())
                else:
                    details.show_requests_unavailable()
        elif request.provisional and shown.record_key is None:
            details.show_requests(message.requests, self.clock())
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
            "dashboard": "tab pane · enter open run",
            "history": "b browse · l list · enter open · s/</> sort · S reverse · x excluded",
            "details": "esc back · [ ] tabs · ↑↓ pgup pgdn scroll",
        }[self._current]
        keys = _tag(muted, f" 1/2/3 views · {hints} · r refresh · ")
        self.query_one("#keys", Static).update(
            keys
            + f"[@click=app.help]{_tag(look.style('accent'), '? keys')}[/]"
            + _tag(muted, " · ")
            + f"[@click=app.quit]{_tag(muted, 'q quit')}[/]"
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
        elif name == "details":
            self.query_one(DetailsView).focus_tab()

    def action_back(self) -> None:
        if self._current == "details":
            self.action_view(self._previous if self._previous != "details" else "dashboard")

    def action_refresh(self) -> None:
        self.poll()

    def action_help(self) -> None:
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen(self.look))

    def on_run_chosen(self, message: RunChosen) -> None:
        details = self.query_one(DetailsView)
        details.open(message.run_id, pinned=message.pinned, record_path=message.record_path)
        self.action_view("details")
        self._refresh_details()


def build_app(monitor: Monitor, look: Theme, **options) -> MonitorApp:
    """The app with the theme's stylesheet; the theme decides every colour and border."""
    themed = type("ThemedMonitorApp", (MonitorApp,), {"CSS": look.css()})
    return themed(monitor, look, **options)
