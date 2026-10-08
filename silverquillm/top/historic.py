"""The historic view: browse the Results Repo by benchmark, Candidate display, or run."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.markup import escape
from textual.widgets import DataTable, Static, Tree

from silverquillm.monitor import RunSummary

from . import format as fmt
from .dashboard import RunChosen
from .theme import Theme
from .widgets import ClickTable


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    sort: Callable[[RunSummary], Any]


def _rate(name: str) -> Callable[[RunSummary], Any]:
    def key(run: RunSummary) -> float:
        score = run.scores.get(name)
        return score.pass_rate if score and score.pass_rate is not None else -1.0

    return key


def _stamp(run: RunSummary) -> float:
    return run.run_date.timestamp() if run.run_date else float("-inf")


COLUMNS = (
    Column("date", "date", _stamp),
    Column("benchmark", "benchmark", lambda run: run.benchmark or ""),
    Column("candidate", "candidate", lambda run: run.candidate.label),
    Column("status", "status", lambda run: run.status or ""),
    Column("target", "target", _rate("card_correctness")),
    Column("fdn", "fdn", _rate("fdn_regression")),
    Column("engine", "engine", _rate("engine_regression")),
    Column(
        "cost", "cost", lambda run: run.estimated_cost if run.estimated_cost is not None else -1
    ),
    Column("duration", "time", lambda run: run.duration_seconds or -1.0),
    Column("turns", "turns", lambda run: run.agent_turns or -1),
    Column("tokens", "tokens", lambda run: run.total_tokens or -1),
    Column("login", "login", lambda run: run.login_profile or ""),
    Column("host", "host", lambda run: run.host_label or ""),
    Column("run", "run", lambda run: run.run_id),
    Column("excluded", "excluded", lambda run: run.excluded or ""),
)
COLUMN_KEYS = [column.key for column in COLUMNS]


def run_cells(run: RunSummary, theme: Theme) -> tuple[Text, ...]:
    """One historic run as one dense line; an excluded run is dimmed.

    Every cell is ``Text``: a table reads a plain string as markup, and these come from records.
    """
    duration = fmt.short_duration(run.duration_seconds)
    if run.budget_seconds:
        duration += f"/{fmt.short_duration(run.budget_seconds)}"
    cost = fmt.money(run.estimated_cost, theme)
    if run.estimated_cost is not None and not run.cost_complete:
        cost.append("*", style=theme.style("muted"))
    login = (run.login_profile or fmt.DASH).rpartition("/")[2]
    excluded = Text(
        f"{theme.glyph('excluded')} {run.excluded}" if run.excluded else "",
        style=theme.style("warn"),
    )
    cells = (
        fmt.when(run.run_date),
        fmt.badge(run.benchmark, theme),
        Text(run.candidate.label, style=theme.style("text")),
        fmt.status(run.status, theme),
        fmt.score(run.scores.get("card_correctness"), theme),
        fmt.score(run.scores.get("fdn_regression"), theme, counts=False),
        fmt.score(run.scores.get("engine_regression"), theme, counts=False),
        cost,
        duration,
        fmt.count(run.agent_turns),
        fmt.count(run.total_tokens),
        login,
        run.host_label or fmt.DASH,
        Text(run.run_id[:8], style=theme.style("muted")),
        excluded,
    )
    cells = tuple(cell if isinstance(cell, Text) else Text(str(cell)) for cell in cells)
    if run.excluded:
        for cell in cells:
            cell.stylize(theme.style("muted"))
    return cells


# Usable width of the browse tree's labels: the pane's 40 columns less border, padding and a
# scrollbar; each level's guides take their share of it.
NAV_LABEL = 34


def _entry(label: Text, total: int, width: int, theme: Theme) -> Text:
    """A tree label cut to fit, its count right-aligned in a column of its own."""
    count = f"{total:>5}"
    room = width - len(count) - 1
    label = label.copy()
    if label.cell_len > room:
        label.truncate(room - 1)
        label.append("…")
    label.pad_right(room - label.cell_len + 1)
    label.append(count, style=theme.style("muted"))
    return label


def _walk(node):
    for child in node.children:
        yield child
        yield from _walk(child)


class HistoryView(Horizontal):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("s", "cycle_sort", "Sort"),
        Binding("greater_than_sign", "cycle_sort", "Next column", show=False),
        Binding("less_than_sign", "cycle_sort(-1)", "Previous column", show=False),
        Binding("S", "reverse_sort", "Reverse"),
        Binding("x", "toggle_excluded", "Excluded"),
        Binding("b", "focus_browse", "Browse", show=False),
        Binding("l", "focus_list", "Runs", show=False),
    ]

    def __init__(self, theme: Theme) -> None:
        super().__init__(id="history")
        self.theme_ = theme
        self.runs: list[RunSummary] = []
        self.selection: tuple[str, Any] = ("all", None)
        self.sort_key = "date"
        self.sort_reverse = True
        self.hide_excluded = False
        self._shown: list[RunSummary] = []
        self._loaded = False
        self._signature: tuple = ()

    def compose(self) -> ComposeResult:
        with Vertical(id="nav", classes="pane") as nav:
            nav.border_title = "BROWSE"
            yield Tree("Results Repo", id="browse")
        with Vertical(id="runs", classes="pane") as runs:
            runs.border_title = "RUNS"
            table = ClickTable(id="runs-table", cursor_type="row")
            for column in COLUMNS:
                table.add_column(column.label, key=column.key)
            yield table
            yield Static("reading the Results Repo…", classes="empty", id="runs-empty")

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        tree.show_root = False
        tree.guide_depth = 2

    def show(self, runs: list[RunSummary]) -> None:
        """Rebuild only when a record or Exclusion changed, so browsing is not reset."""
        signature = tuple(
            (str(run.path), run.excluded, run.status, run.estimated_cost, run.candidate_hash)
            for run in runs
        )
        if self._loaded and signature == self._signature:
            return
        first = not self._loaded
        self._loaded, self._signature, self.runs = True, signature, runs
        self._build_tree(first)
        self._fill()

    def _build_tree(self, first: bool) -> None:
        theme = self.theme_
        tree = self.query_one(Tree)
        expanded = {node.data for node in _walk(tree.root) if node.is_expanded and node.data}
        tree.clear()
        everything = tree.root.add_leaf(
            _entry(
                Text("All runs", style=theme.style("title", bold=True)),
                len(self.runs),
                NAV_LABEL,
                theme,
            ),
            data=("all", None),
        )
        benchmarks = Counter(run.benchmark or fmt.DASH for run in self.runs)
        branch = tree.root.add(
            Text("Benchmarks", style=theme.style("title", bold=True)), data=("group", "benchmarks")
        )
        for benchmark, total in sorted(benchmarks.items()):
            label = _entry(fmt.badge(benchmark, theme), total, NAV_LABEL - 2, theme)
            branch.add_leaf(label, data=("benchmark", benchmark))
        hashes: dict[tuple, Counter] = defaultdict(Counter)
        for run in self.runs:
            hashes[run.candidate.key][run.candidate_hash] += 1
        names: dict[str, list[tuple]] = defaultdict(list)
        for key in hashes:
            names[key[0]].append(key)
        branch = tree.root.add(
            Text("Candidates", style=theme.style("title", bold=True)), data=("group", "candidates")
        )
        for name in sorted(names):
            total = sum(sum(hashes[key].values()) for key in names[name])
            name_node = branch.add(
                _entry(
                    Text(name, style=theme.style("text", bold=True)), total, NAV_LABEL - 4, theme
                ),
                data=("group", name),
            )
            for key in sorted(names[name]):
                settings = f"{key[1]} · {key[2]}"
                node = name_node.add(
                    _entry(Text(settings), sum(hashes[key].values()), NAV_LABEL - 6, theme),
                    data=("candidate", key),
                )
                for candidate_hash, count in hashes[key].most_common():
                    node.add_leaf(
                        _entry(
                            Text(candidate_hash[:8], style=theme.style("accent")),
                            count,
                            NAV_LABEL - 6,
                            theme,
                        ),
                        data=("hash", candidate_hash),
                    )
        for node in _walk(tree.root):
            if node.data in expanded or (first and node.parent is tree.root):
                node.expand()
        if first:
            tree.move_cursor(everything)

    def _matches(self, run: RunSummary) -> bool:
        kind, value = self.selection
        if self.hide_excluded and run.excluded:
            return False
        if kind == "benchmark":
            return (run.benchmark or fmt.DASH) == value
        if kind == "candidate":
            return run.candidate.key == value
        if kind == "hash":
            return run.candidate_hash == value
        return True

    def _fill(self) -> None:
        theme = self.theme_
        table = self.query_one("#runs-table", DataTable)
        column = next(column for column in COLUMNS if column.key == self.sort_key)
        shown = sorted(
            (run for run in self.runs if self._matches(run)),
            key=column.sort,
            reverse=self.sort_reverse,
        )
        if not self.hide_excluded:
            shown.sort(key=lambda run: run.excluded is not None)
        # A row is one Run Record: two records can share a run id under different candidates.
        previous = (
            str(self._shown[table.cursor_row].path)
            if 0 <= table.cursor_row < len(self._shown)
            else None
        )
        self._shown = shown
        table.clear()
        for run in shown:
            table.add_row(*run_cells(run, theme), key=str(run.path))
        order = [str(run.path) for run in shown]
        if previous in order:
            table.move_cursor(row=order.index(previous), animate=False)
        empty = self.query_one("#runs-empty", Static)
        empty.display = not shown
        if not shown:
            empty.update("no runs" if self._loaded else "reading the Results Repo…")
        arrow = theme.glyph("sort_desc" if self.sort_reverse else "sort_asc")
        kind, value = self.selection
        scope = {
            "all": "all runs",
            "benchmark": f"benchmark {value}",
            "candidate": " · ".join(value) if isinstance(value, tuple) else str(value),
            "hash": f"hash {str(value)[:8]}",
        }.get(kind, "all runs")
        runs_pane = self.query_one("#runs")
        # A border title is markup; the scope names candidate data and must stay literal.
        runs_pane.border_title = f"RUNS · {escape(scope)}"
        excluded = sum(1 for run in shown if run.excluded)
        hidden = "hidden" if self.hide_excluded else f"{excluded} dimmed"
        runs_pane.border_subtitle = (
            f"{len(shown)} runs · sort {column.label} {arrow} · excluded {hidden}"
        )

    @property
    def shown(self) -> list[RunSummary]:
        return list(self._shown)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()
        data = event.node.data
        if not data or data[0] == "group":
            return
        if data[0] == "candidate":
            event.node.expand()
        self.selection = data
        self._fill()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        event.stop()
        key = event.column_key.value
        if key == self.sort_key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key, self.sort_reverse = key, key in ("date", "cost", "turns", "tokens")
        self._fill()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        run = next((run for run in self._shown if str(run.path) == event.row_key.value), None)
        if run is not None:
            self.post_message(RunChosen(run.run_id, pinned=True, record_path=str(run.path)))

    def action_focus_browse(self) -> None:
        self.query_one(Tree).focus()

    def action_focus_list(self) -> None:
        self.query_one("#runs-table", DataTable).focus()

    def action_cycle_sort(self, step: int = 1) -> None:
        index = (COLUMN_KEYS.index(self.sort_key) + step) % len(COLUMN_KEYS)
        self.sort_key = COLUMN_KEYS[index]
        self._fill()

    def action_reverse_sort(self) -> None:
        self.sort_reverse = not self.sort_reverse
        self._fill()

    def action_toggle_excluded(self) -> None:
        self.hide_excluded = not self.hide_excluded
        self._fill()
