"""The capacity view's forms: a Cooldown's window, a profile's Usage Limit, and the y/n before
a Cooldown is removed.

A form refuses what it cannot read, saying why, and stays open; only what it can read closes
it, so nothing half-typed is ever written (RUN-MONITORING.md, Capacity view).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Input, Static

from silverquillm.karn.cooldowns import Cooldown
from silverquillm.karn.definition import KarnError
from silverquillm.karn.usage_limit import UsageLimit

from .theme import Theme

START_HINT = "empty: now · 14:00 · Fri 09:00 · 2026-11-20 09:00 · +3h"
END_HINT = "18:00 · Fri 18:00 · 2026-11-20 18:00 · +3h or 1d from the start"


def _hint(theme: Theme, text: str) -> Static:
    return Static(Text(text, style=theme.style("muted")), classes="form-hint")


def _keys(theme: Theme, save: str) -> Static:
    text = Text("enter", style=theme.style("accent", bold=True))
    text.append(f" {save} · ", style=theme.style("muted"))
    text.append("tab", style=theme.style("accent", bold=True))
    text.append(" next field · ", style=theme.style("muted"))
    text.append("esc", style=theme.style("accent", bold=True))
    text.append(" cancel", style=theme.style("muted"))
    return Static(text, classes="form-keys")


class _Form(ModalScreen):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel", show=False)]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def refuse(self, error: KarnError | str) -> None:
        self.query_one("#form-error", Static).update(
            Text(f"not saved: {error}", style=self.theme_.style("bad", bold=True))
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.submit()

    def submit(self) -> None:
        raise NotImplementedError

    def on_mount(self) -> None:
        self.query(Input).first().focus()


class CooldownForm(_Form):
    """Start, end, scope and note of one Cooldown; ``build`` reads them as ``login cooldown``
    reads its times, and the form closes with the Cooldown only once ``build`` accepts them."""

    def __init__(
        self,
        theme: Theme,
        label: str,
        build: Callable[[str, str, bool, str], Cooldown],
        *,
        fable: bool,
        existing: Cooldown | None = None,
        shown: Callable = str,
    ) -> None:
        super().__init__()
        self.theme_, self.label, self.build = theme, label, build
        self.fable, self.existing, self.shown = fable, existing, shown

    def compose(self) -> ComposeResult:
        theme, existing = self.theme_, self.existing
        title = Text(self.label, style=theme.style("text", bold=True))
        if existing is not None and existing.source != "operator":
            title.append(f"  ({existing.source})", style=theme.style("muted"))
        fields: list = [Static(title)]
        fields += [
            _hint(theme, "start · " + START_HINT),
            Input(
                self.shown(existing.start) if existing else "",
                placeholder="now",
                id="form-start",
            ),
            _hint(theme, "end · " + END_HINT),
            Input(self.shown(existing.end) if existing else "", placeholder="+1h", id="form-end"),
        ]
        if self.fable:
            fields.append(
                Checkbox(
                    "Fable runs only",
                    existing is not None and existing.scope == "fable",
                    id="form-fable",
                )
            )
        fields += [
            _hint(theme, "note · optional"),
            Input((existing.note or "") if existing else "", id="form-note"),
            Static(id="form-error"),
            _keys(theme, "save"),
        ]
        body = Vertical(*fields, id="form", classes="pane")
        body.border_title = "CHANGE COOLDOWN" if existing else "ADD COOLDOWN"
        yield body

    def submit(self) -> None:
        fable = self.fable and self.query_one("#form-fable", Checkbox).value
        try:
            window = self.build(
                self.query_one("#form-start", Input).value,
                self.query_one("#form-end", Input).value,
                fable,
                self.query_one("#form-note", Input).value,
            )
        except KarnError as error:
            self.refuse(error)
            return
        self.dismiss(window)


@dataclass(frozen=True)
class LimitChoice:
    limit: UsageLimit | None
    """The ceilings to set, or None to clear the profile's limit."""


class LimitForm(_Form):
    """A profile's weekly and, for Claude, Fable ceilings; both empty clears the limit."""

    def __init__(
        self,
        theme: Theme,
        label: str,
        read: Callable[[str, str], UsageLimit | None],
        *,
        fable: bool,
        current: UsageLimit | None = None,
    ) -> None:
        super().__init__()
        self.theme_, self.label, self.read = theme, label, read
        self.fable, self.current = fable, current

    @staticmethod
    def _percent(value: float | None) -> str:
        return "" if value is None else f"{value:g}"

    def compose(self) -> ComposeResult:
        theme, current = self.theme_, self.current
        fields: list = [
            Static(Text(self.label, style=theme.style("text", bold=True))),
            _hint(theme, "weekly ceiling · percent of the Estimated Weekly Usage"),
            Input(
                self._percent(current.weekly_percent if current else None),
                placeholder="80",
                id="form-weekly",
            ),
        ]
        if self.fable:
            fields += [
                _hint(theme, "Fable ceiling · percent of the Fable limit; holds back Fable runs"),
                Input(
                    self._percent(current.fable_percent if current else None),
                    placeholder="none",
                    id="form-fable-limit",
                ),
            ]
        fields += [
            _hint(theme, "leave every ceiling empty to clear the limit; setting one checks it"),
            Static(id="form-error"),
            _keys(theme, "save"),
        ]
        body = Vertical(*fields, id="form", classes="pane")
        body.border_title = "USAGE LIMIT"
        yield body

    def submit(self) -> None:
        fable = self.query_one("#form-fable-limit", Input).value if self.fable else ""
        try:
            limit = self.read(self.query_one("#form-weekly", Input).value, fable)
        except KarnError as error:
            self.refuse(error)
            return
        self.dismiss(LimitChoice(limit))


class ConfirmCooldownRemove(ModalScreen[bool]):
    """``y`` removes the selected Cooldown; ``n`` or esc keeps it."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "answer(True)", "Remove", show=False),
        Binding("n,escape", "answer(False)", "Keep", show=False),
    ]

    def __init__(self, theme: Theme, label: str, window: str, source: str) -> None:
        super().__init__()
        self.theme_, self.label, self.window, self.source = theme, label, window, source

    def compose(self) -> ComposeResult:
        theme = self.theme_
        text = Text(f"Remove {self.label}'s Cooldown?\n\n", style=theme.style("text", bold=True))
        text.append(f"{self.window}\n\n")
        if self.source == "usage-limit":
            text.append(
                "Its Usage Limit wrote it; the next run's release checks the limit again.\n\n",
                style=theme.style("muted"),
            )
        text.append("y", style=theme.style("bad", bold=True))
        text.append(" remove · ", style=theme.style("muted"))
        text.append("n", style=theme.style("accent", bold=True))
        text.append(" / esc keep", style=theme.style("muted"))
        body = Vertical(Static(text), id="confirm", classes="pane")
        body.border_title = "REMOVE COOLDOWN"
        yield body

    def action_answer(self, remove: bool) -> None:
        self.dismiss(remove)
