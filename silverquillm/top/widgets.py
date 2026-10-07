"""Widgets shared by the views."""

from __future__ import annotations

from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable


class ClickTable(DataTable):
    """A table whose first click on a row opens it, as Enter does (RUN-MONITORING.md).

    Textual's table opens a row only on a second click. Textual runs this handler before
    the table's own, so a row click is handled here and the table's is skipped; header
    clicks still reach the table and sort.
    """

    async def _on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        row, column = meta.get("row", -1), meta.get("column", -1)
        if row < 0 or column < 0 or row >= self.row_count:
            return
        event.prevent_default()
        event.stop()
        self.cursor_coordinate = Coordinate(row, column)
        self.action_select_cursor()
