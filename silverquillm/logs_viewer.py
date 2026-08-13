"""Tabbed log viewer — live + archived modes.

Single-panel, tab-per-channel terminal viewer over a run's per-channel log files.
Works during a live run (tails files) and for finished runs (static history).

Layout: tab bar + scrollable panel + status footer.
Hotkeys: 1-8 switch tabs, ↑/↓/PgUp/PgDn/Home scrollback, End/G tail, q quit.
"""

from __future__ import annotations

import os
import signal
import sys
import termios
import time
import tty
from pathlib import Path
from typing import TextIO

from silverquillm.telemetry import CHANNEL_FILES

__all__ = ["LogsViewer", "run_viewer", "stream_plain"]

# Ordered channel list for tab display
CHANNEL_ORDER = ["runner", "snapshot", "stdout", "stderr", "error", "edit", "system"]

# ANSI escape helpers
ESC = "\033"
CSI = f"{ESC}["


def _enter_alt_screen(out: TextIO) -> None:
    out.write(f"{CSI}?1049h")
    out.flush()


def _exit_alt_screen(out: TextIO) -> None:
    out.write(f"{CSI}?1049l")
    out.flush()


def _hide_cursor(out: TextIO) -> None:
    out.write(f"{CSI}?25l")
    out.flush()


def _show_cursor(out: TextIO) -> None:
    out.write(f"{CSI}?25h")
    out.flush()


def _move_to(out: TextIO, row: int, col: int) -> None:
    out.write(f"{CSI}{row};{col}H")


def _clear_line(out: TextIO) -> None:
    out.write(f"{CSI}2K")


def _get_terminal_size() -> tuple[int, int]:
    """Return (rows, cols)."""
    size = os.get_terminal_size()
    return size.lines, size.columns


class LogsViewer:
    """Interactive tabbed log viewer.

    Parameters
    ----------
    run_dir : Path
        Directory containing per-channel log files.
    live : bool
        If True, tail files for new content. If False, static view.
    """

    def __init__(self, run_dir: Path, live: bool = False) -> None:
        self.run_dir = run_dir
        self.live = live
        self.out: TextIO = sys.stdout
        self.running = False

        self.channels: list[str] = []
        self.channel_files: dict[str, Path] = {}
        for ch in CHANNEL_ORDER:
            fname = CHANNEL_FILES.get(ch)
            if not fname:
                continue
            fpath = run_dir / fname
            if live or fpath.exists():
                self.channels.append(ch)
                self.channel_files[ch] = fpath

        # Visibility tracking for live mode: hide structurally-empty channels
        # A channel is visible when its backing file exists AND has >0 bytes.
        # Once visible, it never hides again (avoids flicker).
        self._ever_visible: set[str] = set()
        if live:
            for ch in self.channels:
                fpath = self.channel_files.get(ch)
                if fpath and fpath.exists() and fpath.stat().st_size > 0:
                    self._ever_visible.add(ch)
        else:
            # In archived mode all discovered channels are visible
            self._ever_visible = set(self.channels)

        # State — active_tab defaults to first visible channel, or None if none visible
        self.active_tab: int | None = self._first_visible_index()
        self.lines: dict[str, list[str]] = {ch: [] for ch in self.channels}
        self.scroll_offset: int = -1  # -1 means TAIL mode (follow end)
        self.unread: dict[str, int] = {ch: 0 for ch in self.channels}
        self.rows: int = 24
        self.cols: int = 80
        self._old_termios: list | None = None
        self._resized = False
        self._last_discovery: float = 0.0

    @property
    def visible_channels(self) -> list[str]:
        """Channels that should be rendered in the tab bar.

        In live mode, a channel is visible only if it has been seen with >0 bytes
        at least once. In archived mode, all discovered channels are visible.
        """
        return [ch for ch in self.channels if ch in self._ever_visible]

    def _poll_channel_visibility(self) -> bool:
        """Check for newly-appearing files and promote them to visible.

        Returns True if any new channel became visible (requires re-render).
        """
        changed = False
        for ch in self.channels:
            if ch in self._ever_visible:
                continue
            fpath = self.channel_files.get(ch)
            if fpath and fpath.exists():
                try:
                    if fpath.stat().st_size > 0:
                        self._ever_visible.add(ch)
                        changed = True
                except OSError:
                    pass
        return changed

    def _first_visible_index(self) -> int | None:
        """Return the index (in self.channels) of the first visible channel, or None."""
        for i, ch in enumerate(self.channels):
            if ch in self._ever_visible:
                return i
        return None

    @property
    def panel_height(self) -> int:
        """Usable lines for log content (total - tab bar - status bar - borders)."""
        return max(1, self.rows - 3)

    @property
    def active_channel(self) -> str:
        if self.active_tab is None or not self.channels:
            return ""
        return self.channels[self.active_tab]

    def _load_file(self, channel: str) -> list[str]:
        """Load all lines from a channel's file."""
        fpath = self.channel_files.get(channel)
        if not fpath or not fpath.exists():
            return []
        try:
            text = fpath.read_text(errors="replace")
            return text.splitlines()
        except OSError:
            return []

    def _reload_active(self) -> None:
        """Reload the active channel's file content."""
        ch = self.active_channel
        if ch:
            old_count = len(self.lines[ch])
            self.lines[ch] = self._load_file(ch)
            new_count = len(self.lines[ch])
            if self.scroll_offset == -1 and new_count > old_count:
                pass  # TAIL mode, will auto-scroll

    def _reload_all(self) -> None:
        """Reload all channel files (for detecting unread)."""
        for ch in self.channels:
            old_count = len(self.lines[ch])
            self.lines[ch] = self._load_file(ch)
            new_count = len(self.lines[ch])
            if ch != self.active_channel and new_count > old_count:
                self.unread[ch] += new_count - old_count

    def _render_tab_bar(self) -> None:
        """Render the tab bar at row 1."""
        _move_to(self.out, 1, 1)
        _clear_line(self.out)
        parts: list[str] = []
        for i, ch in enumerate(self.channels):
            if ch not in self._ever_visible:
                continue  # Hide structurally-empty channels
            label = f"[{i + 1}] {ch}"
            unread = self.unread.get(ch, 0)
            if unread > 0 and i != self.active_tab:
                label += f"({unread})"
            if i == self.active_tab:
                # Highlighted: reverse video
                parts.append(f"{CSI}7m ▶{label}◀ {CSI}0m")
            else:
                parts.append(f" {label} ")
        line = "".join(parts)
        # Truncate to terminal width
        self.out.write(line[: self.cols])

    def _render_panel(self) -> None:
        """Render the log content panel."""
        ph = self.panel_height

        # Show placeholder if no active channel (no visible channels yet)
        if self.active_tab is None:
            for row_idx in range(ph):
                _move_to(self.out, row_idx + 2, 1)
                _clear_line(self.out)
                if row_idx == ph // 2:
                    msg = "waiting for output..."
                    self.out.write(msg[: self.cols])
            return

        ch = self.active_channel
        lines = self.lines.get(ch, [])

        if self.scroll_offset == -1:
            # TAIL mode: show last ph lines
            start = max(0, len(lines) - ph)
            visible = lines[start: start + ph]
        else:
            start = self.scroll_offset
            visible = lines[start: start + ph]

        for row_idx in range(ph):
            _move_to(self.out, row_idx + 2, 1)
            _clear_line(self.out)
            if row_idx < len(visible):
                text = visible[row_idx]
                self.out.write(text[: self.cols])

    def _render_status(self) -> None:
        """Render the status footer at the bottom row."""
        _move_to(self.out, self.rows, 1)
        _clear_line(self.out)
        mode = "TAIL" if self.scroll_offset == -1 else "SCROLLBACK"
        run_name = self.run_dir.name
        status_type = "live" if self.live else "archived"
        status = f" {mode}  {run_name}  [{status_type}]  q quit  ↑↓ scroll  End live"
        self.out.write(f"{CSI}7m{status[: self.cols]}{' ' * max(0, self.cols - len(status))}{CSI}0m")

    def _render(self) -> None:
        """Full screen render."""
        self._render_tab_bar()
        self._render_panel()
        self._render_status()
        self.out.flush()

    def _switch_tab(self, idx: int) -> None:
        """Switch to a different tab (only if it's a visible channel)."""
        if idx < 0 or idx >= len(self.channels):
            return
        # Only allow switching to visible channels
        if self.channels[idx] not in self._ever_visible:
            return
        self.active_tab = idx
        self.scroll_offset = -1  # Reset to TAIL on tab switch
        self.unread[self.channels[idx]] = 0
        self._reload_active()
        self._render()

    def _scroll_up(self, amount: int = 1) -> None:
        """Enter scrollback or scroll up."""
        lines = self.lines.get(self.active_channel, [])
        ph = self.panel_height
        if len(lines) <= ph:
            return  # nothing to scroll into; stay in TAIL
        if self.scroll_offset == -1:
            self.scroll_offset = max(0, len(lines) - ph)
        new_offset = max(0, self.scroll_offset - amount)
        if new_offset == self.scroll_offset:
            return  # already at top of history
        self.scroll_offset = new_offset
        self._render()

    def _scroll_down(self, amount: int = 1) -> None:
        """Scroll down in scrollback."""
        if self.scroll_offset == -1:
            return  # Already at tail
        lines = self.lines.get(self.active_channel, [])
        ph = self.panel_height
        self.scroll_offset += amount
        if self.scroll_offset >= len(lines) - ph:
            self.scroll_offset = -1  # Return to TAIL
        self._render()

    def _go_tail(self) -> None:
        """Return to TAIL mode."""
        self.scroll_offset = -1
        self._render()

    def _go_home(self) -> None:
        """Go to beginning of file."""
        self.scroll_offset = 0
        self._render()

    def _setup_terminal(self) -> None:
        """Enter raw mode and alternate screen."""
        fd = sys.stdin.fileno()
        self._old_termios = termios.tcgetattr(fd)
        tty.setraw(fd)
        _enter_alt_screen(self.out)
        _hide_cursor(self.out)

    def _restore_terminal(self) -> None:
        """Restore terminal state."""
        _show_cursor(self.out)
        _exit_alt_screen(self.out)
        if self._old_termios is not None:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios)
            self._old_termios = None

    def _handle_resize(self, signum: int, frame: object) -> None:
        self._resized = True

    def _read_key(self) -> str | None:
        """Read a single keypress (blocking with timeout for live refresh)."""
        import select
        fd = sys.stdin.fileno()
        timeout = 0.5 if self.live else 0.1
        rlist, _, _ = select.select([fd], [], [], timeout)
        if not rlist:
            return None
        ch = os.read(fd, 1).decode("utf-8", errors="replace")
        if ch == ESC:
            # Could be escape sequence
            rlist2, _, _ = select.select([fd], [], [], 0.05)
            if rlist2:
                seq = os.read(fd, 5).decode("utf-8", errors="replace")
                if seq.startswith("["):
                    code = seq[1:]
                    if code == "A":
                        return "UP"
                    elif code == "B":
                        return "DOWN"
                    elif code == "5~":
                        return "PGUP"
                    elif code == "6~":
                        return "PGDN"
                    elif code == "H":
                        return "HOME"
                    elif code == "F":
                        return "END"
                return None  # Unknown escape
            return "ESC"
        return ch

    def run(self) -> None:
        """Main event loop."""
        if not self.channels:
            print(f"No log files found in {self.run_dir}", file=sys.stderr)
            return

        self.rows, self.cols = _get_terminal_size()
        self._reload_all()
        self._setup_terminal()

        # Set up signal handlers
        old_sigwinch = signal.signal(signal.SIGWINCH, self._handle_resize)
        old_sigint = signal.getsignal(signal.SIGINT)
        old_sigterm = signal.getsignal(signal.SIGTERM)

        def _cleanup_handler(signum: int, frame: object) -> None:
            self.running = False

        signal.signal(signal.SIGINT, _cleanup_handler)
        signal.signal(signal.SIGTERM, _cleanup_handler)

        self.running = True
        last_reload = time.time()
        self._last_discovery = time.time()

        try:
            self._render()
            while self.running:
                if self._resized:
                    self._resized = False
                    self.rows, self.cols = _get_terminal_size()
                    # Clamp scroll_offset to valid range after resize
                    if self.scroll_offset != -1:
                        ch = self.active_channel
                        lines = self.lines.get(ch, [])
                        max_offset = max(0, len(lines) - self.panel_height)
                        self.scroll_offset = min(self.scroll_offset, max_offset)
                    self._render()

                key = self._read_key()

                # Periodic reload in live mode
                if self.live and time.time() - last_reload > 1.0:
                    self._reload_all()
                    if self.scroll_offset == -1:
                        self._render()
                    last_reload = time.time()

                # Periodic channel discovery poll (every 2s)
                if self.live and time.time() - self._last_discovery > 2.0:
                    if self._poll_channel_visibility():
                        # If active_tab was placeholder, switch to first visible
                        if self.active_tab is None:
                            self.active_tab = self._first_visible_index()
                        self._render()
                    self._last_discovery = time.time()

                if key is None:
                    continue
                elif key == "q":
                    break
                elif key in "12345678":
                    self._switch_tab(int(key) - 1)
                elif key == "UP":
                    self._scroll_up()
                elif key == "DOWN":
                    self._scroll_down()
                elif key == "PGUP":
                    self._scroll_up(self.panel_height)
                elif key == "PGDN":
                    self._scroll_down(self.panel_height)
                elif key == "HOME":
                    self._go_home()
                elif key == "END" or key == "G":
                    self._go_tail()
        finally:
            self._restore_terminal()
            signal.signal(signal.SIGWINCH, old_sigwinch)
            signal.signal(signal.SIGINT, old_sigint)
            signal.signal(signal.SIGTERM, old_sigterm)


def stream_plain(run_dir: Path, live: bool = False) -> None:
    """Non-TTY fallback: interleaved plain streaming with channel labels.

    Prints all channel content with [channel] prefix, optionally tailing.
    """
    channel_positions: dict[str, int] = {}
    channels_to_watch: list[str] = []

    for ch in CHANNEL_ORDER:
        fname = CHANNEL_FILES.get(ch)
        if fname:
            fpath = run_dir / fname
            if fpath.exists():
                channels_to_watch.append(ch)
                channel_positions[ch] = 0

    if not channels_to_watch and not live:
        print(f"No log files found in {run_dir}", file=sys.stderr)
        return

    def _dump_new(ch: str) -> None:
        fpath = run_dir / CHANNEL_FILES[ch]
        if not fpath.exists():
            return
        try:
            with open(fpath, "r", errors="replace") as f:
                f.seek(channel_positions.get(ch, 0))
                for line in f:
                    print(f"[{ch}] {line}", end="")
                channel_positions[ch] = f.tell()
        except OSError:
            pass

    def _discover_new_channels() -> None:
        """Poll for channel files that have appeared since startup."""
        for ch in CHANNEL_ORDER:
            if ch in channel_positions:
                continue
            fname = CHANNEL_FILES.get(ch)
            if fname:
                fpath = run_dir / fname
                if fpath.exists():
                    channels_to_watch.append(ch)
                    channel_positions[ch] = 0

    # Initial dump
    for ch in channels_to_watch:
        _dump_new(ch)

    if not live:
        return

    # Tail mode — poll for new content and late-appearing files
    try:
        while True:
            time.sleep(1.0)
            _discover_new_channels()
            for ch in channels_to_watch:
                _dump_new(ch)
    except KeyboardInterrupt:
        pass


def run_viewer(run_dir: Path, live: bool = False) -> None:
    """Entry point: choose TTY viewer or plain fallback."""
    if sys.stdout.isatty() and sys.stdin.isatty():
        viewer = LogsViewer(run_dir, live=live)
        viewer.run()
    else:
        stream_plain(run_dir, live=live)
