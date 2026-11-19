"""The capacity view: what decides whether a new run can claim a Login Profile or a GPU Slot.

One table per Login Pool, then the host's GPU Slots and any orphaned GPU schedules; below
them, the Cooldown Schedule of the selected row. Its keys add, change and remove Cooldowns,
set Usage Limits, and add, re-enroll and remove slots as the LOGINS pane does
(RUN-MONITORING.md, Capacity view).
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Static

from silverquillm.karn.cooldowns import Cooldown
from silverquillm.karn.login_admin import AGENTS
from silverquillm.karn.usage_limit import UsageLimit
from silverquillm.monitor import GpuSlotStatus, MonitorSnapshot, ProfileView
from silverquillm.monitor.headless import login_state

from . import format as fmt
from .cooldowns import Target
from .dashboard import POOLS, EnrollWanted, GpuSlotsPanel, LoginsPane, RemoveWanted
from .theme import Theme

GPUS = "gpus"
POOL_COLUMNS = ("profile", "state", "run", "weekly", "Fable", "limit", "hold")
GPU_COLUMNS = ("gpu slot", "state", "run", "gpus", "memory", "hold")
SCHEDULE_COLUMNS = ("", "start", "end", "scope", "source", "set", "note")


class ScheduleWanted(Message):
    """``n`` (``existing`` None) or ``e`` on a Cooldown of the selected profile or GPU Slot."""

    def __init__(self, target: Target, existing: Cooldown | None, *, fable: bool) -> None:
        super().__init__()
        self.target, self.existing = target, existing
        self.fable = fable
        """The form offers the Fable-only scope: a Claude Login Profile's schedule."""


class CooldownRemoveWanted(Message):
    """``x`` on a Cooldown; the app confirms before anything is removed."""

    def __init__(self, target: Target, cooldown: Cooldown) -> None:
        super().__init__()
        self.target, self.cooldown = target, cooldown


class LimitWanted(Message):
    """``L`` on a Login Profile, with its limit as the view last read it."""

    def __init__(self, plugin_id: str, slot: str, current: UsageLimit | None) -> None:
        super().__init__()
        self.plugin_id, self.slot, self.current = plugin_id, slot, current


def window_text(cooldown: Cooldown) -> str:
    """A Cooldown's window in local time, as the schedule lists it."""
    return f"{fmt.stamp(cooldown.start)} → {fmt.stamp(cooldown.end)}"


def limit_text(limit: UsageLimit | None, theme: Theme) -> Text:
    if limit is None:
        return Text(fmt.DASH, style=theme.style("muted"))
    parts = []
    if limit.weekly_percent is not None:
        parts.append(f"weekly {limit.weekly_percent:g}%")
    if limit.fable_percent is not None:
        parts.append(f"Fable {limit.fable_percent:g}%")
    return Text(theme.glyph("sep").join(parts), style=theme.style("text"))


def _hold(
    until: datetime | None, fable_until: datetime | None, upcoming, now: datetime, theme: Theme
) -> Text:
    if until is not None:
        return fmt.cooldown(until, now, theme, short=True)
    if fable_until is not None:
        return fmt.cooldown(fable_until, now, theme, short=True, fable=True)
    if upcoming is not None:
        return fmt.scheduled(upcoming, theme)
    return Text("")


def profile_cells(view: ProfileView, now: datetime, theme: Theme) -> tuple[Text, ...]:
    status = view.status
    name = LoginsPane.profile(view, now, theme, short=True)[0]
    state = login_state(status)
    roles = {"pending": "bad", "blocked": "bad", "cooldown": "cooldown", "busy": "text"}
    run = Text(view.run_id[:8] if view.run_id else fmt.DASH, style=theme.style("muted"))
    fable = (
        fmt.weekly(view.fable, now, theme, short=True)
        if view.fable is not None
        else Text(fmt.DASH, style=theme.style("muted"))
    )
    return (
        name,
        Text(state, style=theme.style(roles.get(state, "muted"))),
        run,
        fmt.weekly(view.weekly, now, theme, short=True),
        fable,
        limit_text(status.usage_limit, theme),
        _hold(status.cooldown_until, status.fable_cooldown_until, status.next_cooldown, now, theme),
    )


def gpu_cells(status: GpuSlotStatus, now: datetime, theme: Theme) -> tuple[Text, ...]:
    name, names, bar, _ = GpuSlotsPanel.row(status, theme, now)
    gpus = status.gpus or ()
    used = [gpu.get("memory_used_mib") for gpu in gpus]
    total = [gpu.get("memory_total_mib") for gpu in gpus]
    memory = bar.copy()
    if gpus and all(isinstance(value, int | float) for value in used + total):
        memory.append(f" {sum(used) / 1024:.0f}/{sum(total) / 1024:.0f} GiB", style="")
    roles = {"held": "text", "cooldown": "cooldown", "busy": "bad", "unusable": "bad"}
    state = status.state
    return (
        name,
        Text(state, style=theme.style(roles.get(state, "muted"))),
        Text(status.run_id[:8] if status.run_id else fmt.DASH, style=theme.style("muted")),
        names,
        memory,
        _hold(status.cooldown_until, None, status.next_cooldown, now, theme),
    )


def orphan_cells(value: str, theme: Theme) -> tuple[Text, ...]:
    muted = theme.style("muted")
    name = Text(f"{theme.glyph('problem')} gpu {value}", style=theme.style("warn"))
    return (
        name,
        Text("orphaned", style=theme.style("warn")),
        Text(fmt.DASH, style=muted),
        Text("not in gpu_slots: holds back nothing", style=muted),
        Text("", style=muted),
        Text("", style=muted),
    )


def schedule_cells(cooldown: Cooldown, now: datetime, theme: Theme) -> tuple[Text, ...]:
    muted = theme.style("muted")
    current = cooldown.in_force(now)
    mark = Text(
        theme.glyph("cooldown") if current else theme.glyph("scheduled"),
        style=theme.style("cooldown" if current else "muted", bold=current),
    )
    text = theme.style("text", bold=current)
    return (
        mark,
        Text(fmt.stamp(cooldown.start), style=text),
        Text(fmt.stamp(cooldown.end), style=text),
        Text("Fable runs" if cooldown.scope == "fable" else "every run", style=muted),
        Text(cooldown.source, style=theme.style("warn" if cooldown.source != "operator" else "")),
        Text(fmt.stamp(cooldown.set_at), style=muted),
        Text(cooldown.note or "", style=muted),
    )


class CapacityView(Vertical):
    """Every Login Pool and GPU Slot, and the Cooldown Schedule of the one selected."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "add_cooldown", "Add cooldown", show=False),
        Binding("e", "edit_cooldown", "Change cooldown", show=False),
        Binding("x", "remove_cooldown", "Remove cooldown", show=False),
        Binding("L", "limit", "Usage Limit", show=False),
        Binding("a", "add_slot", "Add slot", show=False),
        Binding("R", "refresh_login", "Re-enroll", show=False),
        Binding("D", "remove_slot", "Remove slot", show=False),
    ]

    def __init__(self, theme: Theme) -> None:
        super().__init__(id="capacity")
        self.theme_ = theme
        self.snapshot: MonitorSnapshot | None = None
        self.selected: Target | None = None
        """The row whose schedule is shown, by identity, so a refresh keeps it selected."""
        self._rows: dict[str, list[Target]] = {}
        self._schedule: list[Cooldown] = []

    def compose(self) -> ComposeResult:
        tables = VerticalScroll(id="capacity-tables", classes="pane")
        tables.border_title = "CAPACITY"
        with tables:
            for provider in POOLS:
                yield Static(id=f"capacity-title-{provider}", classes="capacity-title")
                yield self._table(f"capacity-{provider}", POOL_COLUMNS)
            yield Static(id="capacity-title-gpus", classes="capacity-title")
            yield self._table("capacity-gpus", GPU_COLUMNS)
        schedule = Vertical(id="capacity-schedule", classes="pane")
        schedule.border_title = "COOLDOWN SCHEDULE"
        with schedule:
            yield self._table("schedule-table", SCHEDULE_COLUMNS)
            yield Static(id="schedule-empty", classes="empty")

    @staticmethod
    def _table(table_id: str, columns: tuple[str, ...]) -> DataTable:
        table = DataTable(id=table_id, cursor_type="row", classes="capacity-table")
        for label in columns:
            table.add_column(label, key=label or "mark")
        return table

    def focus_first(self) -> None:
        tables = [table for table in self._resource_tables() if table.display and table.row_count]
        (tables[0] if tables else self.query_one("#schedule-table", DataTable)).focus()

    def _resource_tables(self) -> list[DataTable]:
        return [self.query_one(f"#capacity-{key}", DataTable) for key in (*POOLS, GPUS)]

    # Drawing ---------------------------------------------------------------

    def show(self, snapshot: MonitorSnapshot) -> None:
        self.snapshot = snapshot
        theme, now = self.theme_, snapshot.taken_at
        for provider in POOLS:
            views = LoginsPane.views(snapshot, provider)
            targets = [Target(view.status.plugin_id, view.status.slot) for view in views]
            free = sum(1 for view in views if view.status.free)
            title = Text(f"{provider.upper()} pool", style=theme.style(fmt.provider_role(provider)))
            title.stylize("bold")
            title.append(f"  {free}/{len(views)} untapped", style=theme.style("muted"))
            if not views:
                title.append("  none enrolled", style=theme.style("muted"))
            self.query_one(f"#capacity-title-{provider}", Static).update(title)
            rows = [profile_cells(view, now, theme) for view in views]
            self._fill(f"capacity-{provider}", targets, rows)
        gpu_targets = [Target(None, status.value or "") for status in snapshot.gpu_slots]
        gpu_rows = [gpu_cells(status, now, theme) for status in snapshot.gpu_slots]
        for orphan in snapshot.orphaned_gpu_schedules:
            gpu_targets.append(Target(None, orphan.value, orphaned=True))
            gpu_rows.append(orphan_cells(orphan.value, theme))
        shown = bool(gpu_rows)
        self.query_one("#capacity-title-gpus", Static).display = shown
        self.query_one("#capacity-gpus", DataTable).display = shown
        if shown:
            free = sum(1 for status in snapshot.gpu_slots if status.state == "free")
            title = Text("GPU slots", style=theme.style("text", bold=True))
            title.append(f"  {free}/{len(snapshot.gpu_slots)} free", style=theme.style("muted"))
            self.query_one("#capacity-title-gpus", Static).update(title)
        self._fill("capacity-gpus", gpu_targets, gpu_rows)
        everything = [target for targets in self._rows.values() for target in targets]
        if self.selected not in everything:
            self.selected = None
        self._show_schedule()

    def _fill(self, table_id: str, targets: list[Target], rows: list[tuple]) -> None:
        table = self.query_one(f"#{table_id}", DataTable)
        previous = self._rows.get(table_id, [])
        cursor = previous[table.cursor_row] if 0 <= table.cursor_row < len(previous) else None
        table.clear()
        for target, cells in zip(targets, rows, strict=True):
            table.add_row(*cells, key=f"{target.plugin_id}:{target.name}:{target.orphaned}")
        # A fixed height, the rows and the header, so stacked tables never miss a relayout.
        table.styles.height = len(rows) + 1
        self._rows[table_id] = targets
        if cursor in targets:
            table.move_cursor(row=targets.index(cursor), animate=False)

    def _cooldowns_of(self, target: Target | None) -> list[Cooldown]:
        snapshot = self.snapshot
        if target is None or snapshot is None:
            return []
        if not target.gpu:
            for view in snapshot.profiles:
                if (view.status.plugin_id, view.status.slot) == (target.plugin_id, target.name):
                    return list(view.status.cooldowns)
            return []
        if target.orphaned:
            for orphan in snapshot.orphaned_gpu_schedules:
                if orphan.value == target.name:
                    return list(orphan.cooldowns)
            return []
        for status in snapshot.gpu_slots:
            if status.value == target.name:
                return list(status.cooldowns)
        return []

    def _show_schedule(self) -> None:
        theme = self.theme_
        table = self.query_one("#schedule-table", DataTable)
        chosen = self.selected_cooldown
        self._schedule = self._cooldowns_of(self.selected)
        table.clear()
        now = self.snapshot.taken_at if self.snapshot else None
        for index, cooldown in enumerate(self._schedule):
            table.add_row(*schedule_cells(cooldown, now, theme), key=str(index))
        if chosen in self._schedule:
            table.move_cursor(row=self._schedule.index(chosen), animate=False)
        empty = self.query_one("#schedule-empty", Static)
        table.display = bool(self._schedule)
        empty.display = not self._schedule
        pane = self.query_one("#capacity-schedule")
        if self.selected is None:
            pane.border_subtitle = ""
            empty.update(Text("select a Login Profile or GPU Slot", style=theme.style("muted")))
        else:
            pane.border_subtitle = self.selected.label
            empty.update(
                Text(
                    f"{self.selected.label} has no Cooldown · n adds one",
                    style=theme.style("muted"),
                )
            )

    # Selection -------------------------------------------------------------

    @property
    def selected_cooldown(self) -> Cooldown | None:
        table = self.query_one("#schedule-table", DataTable)
        if 0 <= table.cursor_row < len(self._schedule):
            return self._schedule[table.cursor_row]
        return None

    def _select_from(self, table: DataTable) -> None:
        targets = self._rows.get(table.id or "", [])
        if 0 <= table.cursor_row < len(targets) and targets[table.cursor_row] != self.selected:
            self.selected = targets[table.cursor_row]
            self._show_schedule()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Rebuilding a table highlights its cursor row too; only the operator's own move,
        # on the table they are in, changes which row is selected.
        if event.data_table.id in self._rows and event.data_table.has_focus:
            self._select_from(event.data_table)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        if isinstance(event.widget, DataTable) and event.widget.id in self._rows:
            self._select_from(event.widget)

    # Keys ------------------------------------------------------------------

    def _need(self, what: str) -> None:
        self.app.notify(f"select {what} first")

    def _profile(self) -> Target | None:
        target = self.selected
        if target is None or target.gpu:
            self._need("a Login Profile")
            return None
        return target

    def _claude(self, target: Target) -> bool:
        return target.plugin_id == AGENTS["claude"]

    def action_add_cooldown(self) -> None:
        target = self.selected
        if target is None:
            self._need("a Login Profile or GPU Slot")
        elif target.orphaned:
            self.app.notify(f"{target.label} is not in gpu_slots: it takes no Cooldown")
        elif target.gpu and not target.name:
            self.app.notify("list gpu_slots to give the host's GPUs Cooldowns")
        else:
            self.post_message(ScheduleWanted(target, None, fable=self._claude(target)))

    def action_edit_cooldown(self) -> None:
        cooldown = self.selected_cooldown
        if self.selected is None or cooldown is None:
            self._need("a Cooldown")
        elif self.selected.orphaned:
            self.app.notify(f"{self.selected.label} is not in gpu_slots: x removes its Cooldowns")
        else:
            target = self.selected
            self.post_message(ScheduleWanted(target, cooldown, fable=self._claude(target)))

    def action_remove_cooldown(self) -> None:
        cooldown = self.selected_cooldown
        if self.selected is None or cooldown is None:
            self._need("a Cooldown")
        else:
            self.post_message(CooldownRemoveWanted(self.selected, cooldown))

    def action_limit(self) -> None:
        target = self._profile()
        if target is not None:
            current = next(
                (
                    view.status.usage_limit
                    for view in (self.snapshot.profiles if self.snapshot else ())
                    if (view.status.plugin_id, view.status.slot) == (target.plugin_id, target.name)
                ),
                None,
            )
            self.post_message(LimitWanted(target.plugin_id, target.name, current))

    def action_add_slot(self) -> None:
        focused = self.app.focused
        provider = next(
            (p for p in POOLS if focused is not None and focused.id == f"capacity-{p}"), None
        )
        if provider is None and self.selected is not None and not self.selected.gpu:
            provider = next(p for p, plugin in AGENTS.items() if plugin == self.selected.plugin_id)
        if provider is None:
            self._need("a Login Pool")
            return
        self.post_message(EnrollWanted(AGENTS[provider], None))

    def action_refresh_login(self) -> None:
        target = self._profile()
        if target is not None:
            self.post_message(EnrollWanted(target.plugin_id, target.name))

    def action_remove_slot(self) -> None:
        target = self._profile()
        if target is not None:
            self.post_message(RemoveWanted(target.plugin_id, target.name))
