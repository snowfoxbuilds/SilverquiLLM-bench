"""The Textual application: four views over one ``Monitor``, polled off the UI thread."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding, BindingType
from textual.markup import escape
from textual.message import Message
from textual.timer import Timer
from textual.widgets import ContentSwitcher, Static

from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_admin import PROVIDER_OF, remove_slot, slot_identity
from silverquillm.monitor import LogLine, Monitor, MonitorSnapshot, RunSummary, WorkspaceView

from . import cooldowns, limits, slots
from . import format as fmt
from .capacity import (
    CapacityView,
    CooldownRemoveWanted,
    LimitWanted,
    ScheduleWanted,
    window_text,
)
from .dashboard import (
    CooldownWanted,
    DashboardView,
    EnrollWanted,
    PoolPanel,
    RemoveWanted,
    RunChosen,
)
from .details import DetailsView
from .forms import ConfirmCooldownRemove, CooldownForm, LimitChoice, LimitForm
from .historic import HistoryView
from .keys import HelpScreen
from .theme import Theme

VIEWS = (
    ("dashboard", "1", "Dashboard"),
    ("history", "2", "History"),
    ("details", "3", "Run"),
    ("capacity", "4", "Capacity"),
)


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


def _reason(error: BaseException | None) -> str:
    return str(error) if isinstance(error, KarnError) else type(error).__name__


def _tag(style: str, text: str) -> str:
    return f"[{style}]{text}[/]" if style and style != "none" else text


class MonitorApp(App):
    """Every monitor call runs in a worker, and nothing here locks; the only writes are
    those the operator asks for from the LOGINS pane and the capacity view: Cooldowns, Usage
    Limits, and slots signed in or removed (RUN-MONITORING.md, Command and scope)."""

    ENABLE_COMMAND_PALETTE = False
    # The LOGINS pools come first on screen, but the running runs are what opens on start.
    AUTO_FOCUS = "#running-table"
    TITLE = "silverquillm top"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("1", "view('dashboard')", "Dashboard", show=False),
        Binding("2", "view('history')", "History", show=False),
        Binding("3", "view('details')", "Run", show=False),
        Binding("4", "view('capacity')", "Capacity", show=False),
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
            yield CapacityView(self.look)
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
        self.query_one(CapacityView).show(snapshot)
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
        profiles = isinstance(self.focused, PoolPanel)
        hints = {
            "dashboard": "↑↓ slot · ←→ pool · t cooldown +1h · c end now · a add · R re-enroll · D remove"
            if profiles
            else "tab pane · enter open run",
            "history": "b browse · l list · enter open · s/</> sort · S reverse · x excluded",
            "details": "esc back · [ ] tabs · ↑↓ pgup pgdn scroll",
            "capacity": "tab table · ↑↓ select · n add · e change · x remove · L limit"
            " · a add slot · R re-enroll · D remove slot",
        }[self._current]
        keys = _tag(muted, f" 1/2/3/4 views · {hints} · r refresh · ")
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
        elif name == "capacity":
            self.query_one(CapacityView).focus_first()

    def action_back(self) -> None:
        if self._current == "details":
            self.action_view(self._previous if self._previous != "details" else "dashboard")

    def action_refresh(self) -> None:
        self.poll()

    def action_help(self) -> None:
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen(self.look))

    def on_descendant_focus(self) -> None:
        self._draw_bars()

    def on_cooldown_wanted(self, message: CooldownWanted) -> None:
        """Write the cooldown through the CLI's own path, then refresh at once to show it."""
        state_root = self._state_root("set a cooldown")
        if state_root is None:
            return
        now = self.clock()
        try:
            if message.lengthen:
                held = cooldowns.lengthen(state_root, message.plugin_id, message.slot, now=now)
                until, kind = held.end, "fable cooldown" if held.scope == "fable" else "cooldown"
            else:
                until = cooldowns.end_soon(state_root, message.plugin_id, message.slot, now=now)
        except (KarnError, OSError) as error:
            self.notify(f"{message.slot}: cooldown not written ({error})", severity="error")
            return
        if until is None:
            self.notify(f"{message.slot} has no cooldown in force to end")
            return
        local = until.astimezone()
        if message.lengthen:
            self.notify(f"{message.slot} {kind} until {local:%a %H:%M} (+1h)")
        else:
            self.notify(f"{message.slot} cooldown ends at {local:%H:%M:%S} (in 10s)")
        self.poll()

    def _state_root(self, action: str) -> Path | None:
        location = self.snapshot.locations.get("state_root") if self.snapshot else None
        if location is None or location.path is None:
            self.notify(f"no state root: cannot {action}", severity="error")
            return None
        return location.path

    def on_enroll_wanted(self, message: EnrollWanted) -> None:
        """Sign in outside the TUI: the URL and pasted code need the plain terminal."""
        state_root = self._state_root("enroll a slot")
        if state_root is None:
            return
        try:
            with self.suspend():
                outcome = slots.sign_in(state_root, message.plugin_id, message.slot)
        except SuspendNotSupported:
            self.notify(
                "this terminal cannot hand over to a sign-in; use `silverquillm login`",
                severity="error",
            )
            return
        failed = not outcome.endswith(" enrolled")
        self.notify(outcome, severity="error" if failed else "information")
        self.poll()

    def on_remove_wanted(self, message: RemoveWanted) -> None:
        state_root = self._state_root("remove a slot")
        if state_root is None:
            return
        ref = f"{message.plugin_id}/{message.slot}"
        agent = PROVIDER_OF[message.plugin_id]
        try:
            # The confirmation is for this slot as it is now, never a successor of its name.
            identity = slot_identity(state_root, agent, message.slot)
        except (KarnError, OSError) as error:
            self.notify(f"{ref}: not removed ({error})", severity="error")
            return

        def answered(remove: bool | None) -> None:
            if not remove:
                return
            try:
                remove_slot(state_root, agent, message.slot, identity=identity)
            except (KarnError, OSError) as error:
                self.notify(f"{ref}: not removed ({error})", severity="error")
                return
            self.notify(f"{ref} removed")
            self.poll()

        self.push_screen(slots.ConfirmRemove(self.look, ref), answered)

    def on_schedule_wanted(self, message: ScheduleWanted) -> None:
        """A form for the Cooldown, then the write through the CLI's own path."""
        state_root = self._state_root("write a cooldown")
        if state_root is None:
            return
        target, existing = message.target, message.existing

        def build(start: str, end: str, fable: bool, note: str, extend: bool):
            return cooldowns.window(
                start,
                end,
                now=self.clock(),
                fable=fable,
                note=note,
                source=existing.source if existing else "operator",
                extend=extend,
                keep=existing,
                shown=fmt.stamp,
            )

        def answered(window) -> None:
            if window is None:
                return
            now = self.clock()
            try:
                if existing is None:
                    cooldowns.add(state_root, target, window, now=now)
                else:
                    window = cooldowns.replace(state_root, target, existing, window, now=now)
            except (KarnError, OSError) as error:
                self.notify(f"{target.label}: cooldown not written ({error})", severity="error")
                return
            scope = " for Fable runs" if window.scope == "fable" else ""
            done = "changed" if existing else "added"
            ends = "; ends on time" if target.gpu and not window.extend else ""
            self.notify(f"{target.label}: cooldown {done}{scope}, {window_text(window)}{ends}")
            self.poll()

        form = CooldownForm(
            self.look,
            target.label,
            build,
            fable=message.fable,
            extend=target.gpu and not target.orphaned,
            existing=existing,
            shown=fmt.stamp,
        )
        self.push_screen(form, answered)

    def on_cooldown_remove_wanted(self, message: CooldownRemoveWanted) -> None:
        state_root = self._state_root("remove a cooldown")
        if state_root is None:
            return
        target, old = message.target, message.cooldown

        def answered(remove: bool | None) -> None:
            if not remove:
                return
            try:
                found = cooldowns.remove(state_root, target, old, now=self.clock())
            except (KarnError, OSError) as error:
                self.notify(f"{target.label}: cooldown not removed ({error})", severity="error")
                return
            if found:
                self.notify(f"{target.label}: cooldown removed, {window_text(old)}")
            else:
                self.notify(f"{target.label}: that cooldown had already ended or gone")
            self.poll()

        confirm = ConfirmCooldownRemove(self.look, target.label, window_text(old), old.source)
        self.push_screen(confirm, answered)

    def on_limit_wanted(self, message: LimitWanted) -> None:
        """A form for the ceilings; setting one checks it off the UI thread, since the check
        reads the host's history."""
        state_root = self._state_root("set a usage limit")
        if state_root is None:
            return
        plugin_id, slot = message.plugin_id, message.slot
        ref = f"{plugin_id}/{slot}"
        claude = PROVIDER_OF.get(plugin_id) == "claude"

        def read(weekly: str, fable: str):
            if fable.strip() and not claude:
                raise KarnError("fable_limit_claude_only")
            return limits.ceilings(weekly, fable)

        def answered(choice: LimitChoice | None) -> None:
            if choice is None:
                return
            if choice.limit is None:
                try:
                    had = limits.clear(state_root, plugin_id, slot)
                except (KarnError, OSError) as error:
                    self.notify(f"{ref}: limit not cleared ({error})", severity="error")
                    return
                self.notify(f"{ref}: limit removed" if had else f"{ref} had no limit")
                self.poll()
                return
            self._check_limit(state_root, plugin_id, slot, choice.limit)

        form = LimitForm(self.look, ref, read, fable=claude, current=message.current)
        self.push_screen(form, answered)

    def _check_limit(self, state_root: Path, plugin_id: str, slot: str, limit) -> None:
        ref = f"{plugin_id}/{slot}"
        now = self.clock()
        # Taken here, on the UI thread, from the snapshot on screen: a poll in flight
        # replaces the snapshot but never changes it, so the check sees what was shown.
        estimated = limits.estimate(self.snapshot, self.monitor.config, plugin_id, slot)

        def work() -> None:
            try:
                written, error = (
                    limits.set_and_check(
                        state_root, plugin_id, slot, limit, now=now, estimated=estimated
                    ),
                    None,
                )
            except Exception as failure:  # noqa: BLE001 -- reported, never a crash of the view
                written, error = [], failure
            try:
                self.call_from_thread(self._limit_checked, ref, limit, written, error)
            except RuntimeError:
                pass  # the app has closed meanwhile; the limit is set or not on disk regardless

        threading.Thread(target=work, name=f"top-limit-{slot}", daemon=True).start()

    def _limit_checked(self, ref: str, limit, written: list, error: Exception | None) -> None:
        if isinstance(error, limits.Unchecked):
            reason = _reason(error.__cause__)
            self.notify(
                f"{ref}: limit saved, but its check could not complete ({reason});"
                " set it again to check it",
                severity="error",
            )
            self.poll()
            return
        if error is not None:
            self.notify(f"{ref}: limit not set ({_reason(error)})", severity="error")
            self.poll()
            return
        ceilings = []
        if limit.weekly_percent is not None:
            ceilings.append(f"weekly {limit.weekly_percent:g}%")
        if limit.fable_percent is not None:
            ceilings.append(f"Fable {limit.fable_percent:g}%")
        self.notify(f"{ref}: limit set, {' · '.join(ceilings)}")
        for cooldown in written:
            held = "Fable runs held" if cooldown.scope == "fable" else "cooling down"
            self.notify(f"{ref}: limit reached; {held} until {fmt.stamp(cooldown.end)}")
        self.poll()

    def on_run_chosen(self, message: RunChosen) -> None:
        details = self.query_one(DetailsView)
        details.open(message.run_id, pinned=message.pinned, record_path=message.record_path)
        self.action_view("details")
        self._refresh_details()


def build_app(monitor: Monitor, look: Theme, **options) -> MonitorApp:
    """The app with the theme's stylesheet; the theme decides every colour and border."""
    themed = type("ThemedMonitorApp", (MonitorApp,), {"CSS": look.css()})
    return themed(monitor, look, **options)
