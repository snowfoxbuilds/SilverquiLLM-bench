"""Slot management from the LOGINS pane: sign-in outside the TUI, and a confirmed removal.

A sign-in prints a long URL and reads a pasted code, so the monitor suspends itself and
the enrollment runs in the plain terminal exactly as ``silverquillm login`` runs it
(RUN-MONITORING.md, Command and scope).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_admin import PROVIDER_OF, enroll_slot

from .theme import Theme


def sign_in(state_root: Path, plugin_id: str, slot: str | None, *, read=input) -> str:
    """Enroll in the plain terminal, wait for the operator, and return a one-line outcome."""
    agent = PROVIDER_OF[plugin_id]
    target = f"{plugin_id}/{slot}" if slot else f"a new {agent} slot"
    print(f"\nsilverquillm top: signing in {target}. Ctrl+C cancels.\n", flush=True)
    try:
        ref, status = enroll_slot(state_root, agent, slot)
        outcome = f"{ref} enrolled" if status == 0 else f"{ref}: sign-in failed (exit {status})"
    except (KarnError, OSError, ValueError) as error:
        outcome = f"{target}: not enrolled ({error})"
    except KeyboardInterrupt:
        outcome = f"{target}: sign-in cancelled"
    print(f"\n{outcome}", flush=True)
    try:
        read("Press Enter to return to top. ")
    except (EOFError, KeyboardInterrupt):
        pass
    return outcome


class ConfirmRemove(ModalScreen[bool]):
    """``y`` removes the slot and its stored login; ``n`` or esc keeps it."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "answer(True)", "Remove", show=False),
        Binding("n,escape", "answer(False)", "Keep", show=False),
    ]

    def __init__(self, theme: Theme, ref: str) -> None:
        super().__init__()
        self.theme_, self.ref = theme, ref

    def compose(self) -> ComposeResult:
        theme = self.theme_
        text = Text(f"Remove {self.ref}?\n\n", style=theme.style("text", bold=True))
        text.append("Its stored login is deleted; re-adding it means signing in again.\n\n")
        text.append("y", style=theme.style("bad", bold=True))
        text.append(" remove · ", style=theme.style("muted"))
        text.append("n", style=theme.style("accent", bold=True))
        text.append(" / esc keep", style=theme.style("muted"))
        body = Vertical(Static(text), id="confirm", classes="pane")
        body.border_title = "REMOVE SLOT"
        yield body

    def action_answer(self, remove: bool) -> None:
        self.dismiss(remove)
