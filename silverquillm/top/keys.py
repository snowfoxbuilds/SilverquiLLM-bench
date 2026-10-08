"""Every key the monitor answers to, and the ``?`` overlay that lists them.

Each mouse action has a key here too, because a terminal may not deliver the mouse at all
(RUN-MONITORING.md, Navigation).
"""

from __future__ import annotations

from typing import ClassVar

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from .theme import Theme

KEYS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Everywhere",
        (
            ("1 2 3", "dashboard, history, run details"),
            ("tab / shift+tab", "move between panes and tables"),
            ("↑ ↓ pgup pgdn home end", "move or scroll within the focused pane"),
            ("enter", "open the selected run"),
            ("esc", "back from run details"),
            ("r", "refresh now"),
            ("?", "this list"),
            ("q", "quit"),
        ),
    ),
    (
        "Dashboard LOGINS pane",
        (
            ("tab / click", "focus a Login Pool and select a profile"),
            ("↑ ↓ / k j", "select the previous / next Login Profile"),
            ("← → / h l", "move to the other pool, or out of the pane"),
            ("t", "cooldown the selected profile for 1h; each press adds 1h"),
            ("c", "end the selected profile's cooldown in 10s"),
        ),
    ),
    (
        "History",
        (
            ("b / l", "focus the browse tree / the run list"),
            ("enter", "browse tree: show that benchmark, candidate or hash"),
            ("space", "browse tree: expand or collapse"),
            ("s / >", "sort by the next column"),
            ("<", "sort by the previous column"),
            ("S", "reverse the sort"),
            ("x", "hide or show excluded runs"),
        ),
    ),
    (
        "Run details",
        (
            ("[ / ]", "previous / next tab"),
            ("↑ ↓ pgup pgdn home end", "scroll the tab's log or table"),
        ),
    ),
)


def help_table(theme: Theme) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=theme.style("accent", bold=True), no_wrap=True)
    table.add_column(style=theme.style("text"))
    for index, (section, rows) in enumerate(KEYS):
        if index:
            table.add_row("", "")
        table.add_row(Text(section, style=theme.style("title", bold=True)), "")
        for keys, action in rows:
            table.add_row(keys, action)
    return table


class HelpScreen(ModalScreen):
    """The key list over the current view; any of esc, ? or q closes it."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self.theme_ = theme

    def compose(self) -> ComposeResult:
        # Bounded by the screen and focused on open, so a short terminal reaches every row
        # by keyboard.
        body = VerticalScroll(Static(help_table(self.theme_)), id="help", classes="pane")
        body.border_title = "KEYS"
        body.border_subtitle = "↑ ↓ pgup pgdn home end scroll · esc closes"
        yield body

    def on_mount(self) -> None:
        self.query_one("#help", VerticalScroll).focus()
