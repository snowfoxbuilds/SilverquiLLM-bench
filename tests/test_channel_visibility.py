"""Tests for channel visibility in live mode with rediscovery polling.

Verifies the TODO item: "Hide structurally-empty channels in live mode with rediscovery polling"
Requirements:
1. A channel is hidden while its backing file doesn't exist or is 0 bytes.
2. A background poller checks for newly-appearing files and promotes them to visible.
3. A channel that was once visible never hides again (avoids flicker).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.logs_viewer import LogsViewer, CHANNEL_ORDER
from silverquillm.telemetry import CHANNEL_FILES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_run_dir(tmp_path: Path) -> Path:
    """A run directory with no channel files."""
    return tmp_path


@pytest.fixture
def partial_run_dir(tmp_path: Path) -> Path:
    """A run directory with some non-empty files and some missing/empty."""
    # runner.log exists with content
    (tmp_path / "runner.log").write_text("hello from runner\n")
    # system.log exists but is empty (0 bytes)
    (tmp_path / "system.log").write_text("")
    # All other channel files don't exist
    return tmp_path


# ---------------------------------------------------------------------------
# Requirement 1: Channel hidden when file doesn't exist or is 0 bytes
# ---------------------------------------------------------------------------


class TestChannelHiddenWhenEmpty:
    """A channel is hidden while its backing file doesn't exist or is 0 bytes."""

    def test_channel_hidden_when_file_does_not_exist(self, empty_run_dir: Path) -> None:
        """In live mode, channels with no backing file are not in visible_channels."""
        viewer = LogsViewer(empty_run_dir, live=True)
        # All channels are in self.channels (live mode enumerates all)
        assert len(viewer.channels) == 8
        # But none should be visible since no files exist
        assert viewer.visible_channels == []

    def test_channel_hidden_when_file_is_zero_bytes(self, tmp_path: Path) -> None:
        """In live mode, channels with a 0-byte file are not in visible_channels."""
        # Create all channel files but all empty
        for ch in CHANNEL_ORDER:
            fname = CHANNEL_FILES.get(ch)
            if fname:
                (tmp_path / fname).write_text("")
        viewer = LogsViewer(tmp_path, live=True)
        assert viewer.visible_channels == []

    def test_channel_visible_when_file_has_content(self, partial_run_dir: Path) -> None:
        """In live mode, channels with >0 byte files are in visible_channels."""
        viewer = LogsViewer(partial_run_dir, live=True)
        assert "runner" in viewer.visible_channels
        # system.log is 0 bytes, so it should NOT be visible
        assert "system" not in viewer.visible_channels

    def test_multiple_channels_independent_visibility(self, tmp_path: Path) -> None:
        """Each channel's visibility is determined independently by its own file."""
        (tmp_path / "runner.log").write_text("content\n")
        (tmp_path / "docker_stdout.log").write_text("output\n")
        (tmp_path / "system.log").write_text("")  # empty
        # Others don't exist
        viewer = LogsViewer(tmp_path, live=True)
        visible = viewer.visible_channels
        assert "runner" in visible
        assert "stdout" in visible
        assert "system" not in visible
        assert "snapshot" not in visible
        assert "error" not in visible


# ---------------------------------------------------------------------------
# Requirement 2: Background poller promotes channels when file appears
# ---------------------------------------------------------------------------


class TestPollerPromotesChannels:
    """Background poller promotes channels to visible when file appears with content."""

    def test_poll_promotes_newly_created_file(self, empty_run_dir: Path) -> None:
        """_poll_channel_visibility promotes a channel when its file appears with content."""
        viewer = LogsViewer(empty_run_dir, live=True)
        assert viewer.visible_channels == []

        # Simulate file appearing with content
        (empty_run_dir / "runner.log").write_text("first line\n")
        changed = viewer._poll_channel_visibility()

        assert changed is True
        assert "runner" in viewer.visible_channels

    def test_poll_does_not_promote_empty_file(self, empty_run_dir: Path) -> None:
        """_poll_channel_visibility does NOT promote a channel if file is still 0 bytes."""
        viewer = LogsViewer(empty_run_dir, live=True)

        # Create file but leave it empty
        (empty_run_dir / "runner.log").write_text("")
        changed = viewer._poll_channel_visibility()

        assert changed is False
        assert "runner" not in viewer.visible_channels

    def test_poll_returns_false_when_nothing_new(self, empty_run_dir: Path) -> None:
        """_poll_channel_visibility returns False when no new channels become visible."""
        viewer = LogsViewer(empty_run_dir, live=True)
        changed = viewer._poll_channel_visibility()
        assert changed is False

    def test_poll_promotes_multiple_channels_at_once(self, empty_run_dir: Path) -> None:
        """Multiple channels can become visible in a single poll cycle."""
        viewer = LogsViewer(empty_run_dir, live=True)

        (empty_run_dir / "runner.log").write_text("data\n")
        (empty_run_dir / "system.log").write_text("data\n")
        changed = viewer._poll_channel_visibility()

        assert changed is True
        assert "runner" in viewer.visible_channels
        assert "system" in viewer.visible_channels

    def test_poll_skips_already_visible_channels(self, tmp_path: Path) -> None:
        """_poll_channel_visibility does not re-check channels already in _ever_visible."""
        (tmp_path / "runner.log").write_text("content\n")
        viewer = LogsViewer(tmp_path, live=True)
        assert "runner" in viewer.visible_channels

        # Polling again should not report a change for runner
        changed = viewer._poll_channel_visibility()
        assert changed is False


# ---------------------------------------------------------------------------
# Requirement 3: Once visible, never hides again
# ---------------------------------------------------------------------------


class TestNeverHideAgain:
    """A channel that was once visible never hides again (avoids flicker)."""

    def test_channel_stays_visible_after_file_deleted(self, tmp_path: Path) -> None:
        """If a file is deleted after being seen, channel remains visible."""
        (tmp_path / "runner.log").write_text("content\n")
        viewer = LogsViewer(tmp_path, live=True)
        assert "runner" in viewer.visible_channels

        # Delete the file
        (tmp_path / "runner.log").unlink()
        # Re-poll should not remove it
        viewer._poll_channel_visibility()
        assert "runner" in viewer.visible_channels

    def test_channel_stays_visible_after_file_truncated(self, tmp_path: Path) -> None:
        """If a file is truncated to 0 bytes after being seen, channel remains visible."""
        (tmp_path / "runner.log").write_text("content\n")
        viewer = LogsViewer(tmp_path, live=True)
        assert "runner" in viewer.visible_channels

        # Truncate to 0 bytes
        (tmp_path / "runner.log").write_text("")
        viewer._poll_channel_visibility()
        assert "runner" in viewer.visible_channels

    def test_ever_visible_set_persists_across_polls(self, empty_run_dir: Path) -> None:
        """The _ever_visible set accumulates channels and never removes them."""
        viewer = LogsViewer(empty_run_dir, live=True)
        assert len(viewer._ever_visible) == 0

        # First channel appears
        (empty_run_dir / "runner.log").write_text("data\n")
        viewer._poll_channel_visibility()
        assert "runner" in viewer._ever_visible

        # Second channel appears
        (empty_run_dir / "system.log").write_text("data\n")
        viewer._poll_channel_visibility()
        assert "runner" in viewer._ever_visible
        assert "system" in viewer._ever_visible

        # Delete both files — both stay in _ever_visible
        (empty_run_dir / "runner.log").unlink()
        (empty_run_dir / "system.log").unlink()
        viewer._poll_channel_visibility()
        assert "runner" in viewer._ever_visible
        assert "system" in viewer._ever_visible


# ---------------------------------------------------------------------------
# Archived mode: all channels visible (no hiding)
# ---------------------------------------------------------------------------


class TestArchivedModeNoHiding:
    """In archived mode, all discovered channels are always visible."""

    def test_archived_mode_shows_all_discovered_channels(self, tmp_path: Path) -> None:
        """In archived mode, every channel with an existing file is visible."""
        (tmp_path / "runner.log").write_text("data\n")
        (tmp_path / "system.log").write_text("")  # Even empty files exist → discovered
        viewer = LogsViewer(tmp_path, live=False)
        # In archived mode, only files that exist are in channels
        # But all discovered channels should be visible
        assert set(viewer.visible_channels) == set(viewer.channels)


# ---------------------------------------------------------------------------
# Tab bar rendering respects visibility
# ---------------------------------------------------------------------------


class TestTabBarVisibility:
    """The tab bar should only show visible channels."""

    def test_visible_channels_preserves_order(self, tmp_path: Path) -> None:
        """visible_channels maintains CHANNEL_ORDER ordering."""
        # Create runner and system with content (not adjacent in CHANNEL_ORDER)
        (tmp_path / "runner.log").write_text("data\n")
        (tmp_path / "system.log").write_text("data\n")
        viewer = LogsViewer(tmp_path, live=True)
        visible = viewer.visible_channels
        # runner comes before system in CHANNEL_ORDER
        assert visible.index("runner") < visible.index("system")
