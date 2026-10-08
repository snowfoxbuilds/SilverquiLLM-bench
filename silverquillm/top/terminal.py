"""The terminal driver: Textual's own, but reporting the mouse in character cells only.

Textual asks a terminal whether it supports in-band resize (mode 2048) and, when it does,
switches to pixel mouse coordinates (mode 1016) and divides each report by the terminal's
pixel size. A multiplexer such as herdr answers the query for its pane, but reached over
mosh it has no real pixel size to convert with, so clicks land in the wrong cell or nowhere.
Cell coordinates (SGR mode 1006) need no pixel size and pass through mosh and multiplexers.
Without the query, resizes still arrive through SIGWINCH.
"""

from __future__ import annotations

from textual.drivers.linux_driver import LinuxDriver


class CellMouseDriver(LinuxDriver):
    def _query_in_band_window_resize(self) -> None:
        pass

    def _enable_mouse_pixels(self) -> None:
        pass
