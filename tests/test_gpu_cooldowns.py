"""GPU Slot Cooldown Schedules: claims, the scheduler's hint, the monitor, and `gpu` commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn.cooldowns import (
    COOLDOWNS_FILE,
    add_cooldown,
    cooldown,
    held_until,
    read_schedule,
)
from silverquillm.karn.definition import KarnError
from silverquillm.karn.model_server import (
    GpuReading,
    ModelServerBusyError,
    claim_gpu_slot,
    gpu_schedule_dir,
    gpu_slot_availability,
    gpu_slots,
    writable_gpu_schedule_dir,
)
from silverquillm.monitor.gpus import GpuSlotStatus, gpu_slot_statuses, orphaned_gpu_schedules
from silverquillm.monitor.headless import snapshot_document

from .test_top_gpu_slots import READING, h100, lock_table_now, monitor
from .top_fixtures import NOW


def _hold(state, value, start, end, *, now, note=None):
    window = cooldown(start, end, now=now, note=note)
    return add_cooldown(writable_gpu_schedule_dir(state, value), window, now=now)


def _free():
    return GpuReading((h100(0), h100(1)))


def test_a_claim_passes_over_a_gpu_slot_with_a_cooldown_in_force(tmp_path):
    now = datetime.now(UTC)
    slots = gpu_slots(tmp_path, ("0", "1"))
    _hold(tmp_path, "0", now, now + timedelta(hours=2), now=now)
    claim = claim_gpu_slot(slots, _free)
    assert claim.slot.value == "1"
    with pytest.raises(ModelServerBusyError, match="model_server_busy") as refused:
        claim_gpu_slot(slots, _free)
    # A Cooldown is not a fault of the slot: nothing is reported unusable.
    assert refused.value.unusable == ()
    claim.release()
    assert gpu_slot_availability(slots, _free, tmp_path / "no-locks")[0]
    assert not gpu_slot_availability(slots[:1], _free, tmp_path / "no-locks")[0]


def test_only_a_cooldown_in_force_holds_a_gpu_slot_back(tmp_path):
    now = datetime.now(UTC)
    slots = gpu_slots(tmp_path, ("0",))
    _hold(tmp_path, "0", now + timedelta(hours=1), now + timedelta(hours=2), now=now)
    claim_gpu_slot(slots, _free).release()
    later = now + timedelta(minutes=90)
    with pytest.raises(ModelServerBusyError):
        claim_gpu_slot(slots, _free, now=later)
    assert not gpu_slot_availability(slots, _free, tmp_path / "no-locks", now=later)[0]
    claim_gpu_slot(slots, _free, now=now + timedelta(hours=3)).release()


def test_a_cooldown_never_takes_a_gpu_slot_from_the_run_holding_it(tmp_path):
    now = datetime.now(UTC)
    slots = gpu_slots(tmp_path, ("0",))
    claim = claim_gpu_slot(slots, _free)
    lock = slots[0].lock_path.read_bytes()
    _hold(tmp_path, "0", now, now + timedelta(hours=1), now=now)
    assert slots[0].lock_path.read_bytes() == lock
    held = lock_table_now(tmp_path)
    (status,) = gpu_slot_statuses(tmp_path, ("0",), held, _free(), [])
    assert status.state == "held" and status.cooldown_until is not None
    claim.release()
    with pytest.raises(ModelServerBusyError):
        claim_gpu_slot(slots, _free)


def test_a_gpu_slot_schedule_is_keyed_by_its_value_and_never_leaves_the_state_root(tmp_path):
    now = datetime.now(UTC)
    _hold(tmp_path, "0,1", now, now + timedelta(hours=1), now=now)
    directory = gpu_schedule_dir(tmp_path, "0,1")
    assert directory == tmp_path.resolve() / "gpu-slots" / "0,1"
    assert (directory / COOLDOWNS_FILE).is_file()
    assert directory.stat().st_mode & 0o777 == 0o700
    # Reordering gpu_slots moves no Cooldown: it stays with its value.
    reordered = gpu_slots(tmp_path, ("2", "0,1"))
    assert reordered[1].cooling_until(now) is not None
    assert reordered[0].cooling_until(now) is None
    for value in ("../0", "0/1", "", "01", "0,", "a"):
        with pytest.raises(KarnError, match="invalid_gpu_slot_value"):
            gpu_schedule_dir(tmp_path, value)


def test_an_unreadable_gpu_slot_schedule_holds_nothing_back(tmp_path):
    directory = writable_gpu_schedule_dir(tmp_path, "0")
    (directory / COOLDOWNS_FILE).write_text("{not json")
    claim_gpu_slot(gpu_slots(tmp_path, ("0",)), _free).release()


def test_a_symlinked_schedule_directory_is_refused_rather_than_written_through(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "state" / "gpu-slots").mkdir(parents=True)
    (tmp_path / "state" / "gpu-slots" / "0").symlink_to(elsewhere)
    with pytest.raises(KarnError, match="gpu_slot_schedule_unusable"):
        writable_gpu_schedule_dir(tmp_path / "state", "0")
    assert list(elsewhere.iterdir()) == []


def test_the_monitor_reads_a_cooldown_after_unusable_and_before_busy(tmp_path):
    state = tmp_path / "state"
    _hold(state, "0", NOW - timedelta(hours=1), NOW + timedelta(hours=2), now=NOW)
    _hold(state, "2", NOW - timedelta(hours=1), NOW + timedelta(hours=2), now=NOW)
    _hold(state, "1", NOW + timedelta(days=1), NOW + timedelta(days=2), now=NOW)
    missing = GpuReading((h100(0), h100(1), h100(2, used=40000)))
    held = lock_table_now(tmp_path)
    statuses = gpu_slot_statuses(state, ("0", "1", "2", "7"), held, missing, [], now=NOW)
    assert [status.state for status in statuses] == ["cooldown", "free", "cooldown", "unusable"]
    assert statuses[0].cooldown_until == NOW + timedelta(hours=2)
    assert statuses[1].next_cooldown == NOW + timedelta(days=1)
    assert statuses[1].cooldown_until is None and len(statuses[1].cooldowns) == 1


def test_top_json_shows_each_gpu_slots_cooldowns_and_the_orphaned_schedules(tmp_path):
    state = tmp_path / "state"
    _hold(state, "0", NOW, NOW + timedelta(hours=3), now=NOW, note="training job")
    _hold(state, "3", NOW + timedelta(hours=1), NOW + timedelta(hours=2), now=NOW)
    # An orphan with nothing left to hold is not worth listing.
    writable_gpu_schedule_dir(state, "5")
    view = monitor(tmp_path, '[model_server]\ngpu_slots = ["0", "2"]\n', lambda: READING)
    try:
        document = snapshot_document(view.snapshot())
    finally:
        view.close()
    first, second = document["gpu_slots"]
    assert first["state"] == "cooldown"
    assert first["cooldown_until"] == "2026-10-07T18:30:00Z"
    assert first["cooldowns"] == [
        {
            "start": "2026-10-07T15:30:00Z",
            "end": "2026-10-07T18:30:00Z",
            "set_at": "2026-10-07T15:30:00Z",
            "scope": "all",
            "source": "operator",
            "note": "training job",
        }
    ]
    assert second["state"] == "busy" and second["cooldowns"] == []
    assert second["cooldown_until"] is None
    (orphan,) = document["orphaned_gpu_schedules"]
    assert orphan["gpu_slot"] == "3" and len(orphan["cooldowns"]) == 1


def test_every_schedule_is_orphaned_on_a_host_that_lists_no_gpu_slots(tmp_path):
    now = datetime.now(UTC)
    _hold(tmp_path, "1", now, now + timedelta(hours=1), now=now)
    assert [orphan.value for orphan in orphaned_gpu_schedules(tmp_path, None)] == ["1"]
    assert orphaned_gpu_schedules(tmp_path, ("1",)) == []


def test_the_gpu_section_marks_a_cooling_slot_and_counts_it_out_of_free():
    pytest.importorskip("textual")
    from silverquillm.top.dashboard import GpuSlotsPanel
    from silverquillm.top.theme import MTG

    from .test_top_cooldowns import _plain

    statuses = [
        GpuSlotStatus("0", False, None, (h100(0),), cooldown_until=NOW + timedelta(hours=3)),
        GpuSlotStatus("1", False, None, (h100(1),), next_cooldown=NOW + timedelta(days=1)),
    ]
    lines = _plain(GpuSlotsPanel.table(statuses, MTG, NOW)).splitlines()
    assert "1/2 free" in lines[0]
    assert MTG.glyph("cooldown") in lines[1] and "cooldown until" in lines[1]
    assert "(3h" in lines[1]
    assert "free" in lines[2] and MTG.glyph("scheduled") in lines[2]


def _configure(tmp_path, monkeypatch, slots: str | None = '["0", "1"]'):
    home = tmp_path / "xdg" / "silverquillm"
    home.mkdir(parents=True)
    state = tmp_path / "state"
    body = f'state_root = "{state}"\n'
    if slots is not None:
        body += f"[model_server]\ngpu_slots = {slots}\n"
    (home / "config.toml").write_text(body)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        "silverquillm.karn.model_server.read_gpus", lambda **_: GpuReading((h100(0), h100(1)))
    )
    return state


def _gpu(*args):
    return CliRunner().invoke(main, ["gpu", *args])


def test_gpu_cooldown_holds_named_slots_and_clear_lifts_them(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    result = _gpu("cooldown", "1", "--duration", "2h", "--note", "render farm")
    assert result.exit_code == 0, result.output
    assert "gpu 1: cooling down until" in result.output
    (window,) = read_schedule(gpu_schedule_dir(state, "1"))
    assert window.note == "render farm" and window.scope == "all"
    assert window.source == "operator"
    assert window.end - window.start == timedelta(hours=2)
    assert held_until(gpu_schedule_dir(state, "0")) is None

    later = _gpu("cooldown", "--all", "--from", "+1d", "--duration", "1h")
    assert later.exit_code == 0, later.output
    assert later.output.count("cooling down from") == 2

    listing = _gpu("ls")
    assert listing.exit_code == 0, listing.output
    lines = listing.output.splitlines()
    assert lines[0].startswith("gpu 0") and "free" in lines[0] and "cooldown from" in lines[0]
    assert any(line.startswith("gpu 1") and "cooldown" in line for line in lines)
    assert any("render farm" in line for line in lines)

    lift = _gpu("cooldown", "--all", "--clear")
    assert lift.exit_code == 0, lift.output
    assert "gpu 1: 2 cooldown(s) removed" in lift.output
    assert read_schedule(gpu_schedule_dir(state, "1")) == []


def test_gpu_cooldown_refuses_slots_the_host_does_not_list_but_clears_orphans(
    tmp_path, monkeypatch
):
    state = _configure(tmp_path, monkeypatch)
    unknown = _gpu("cooldown", "3", "--duration", "1h")
    assert unknown.exit_code == 2
    assert "Not a GPU Slot: 3 (gpu_slots: 0, 1)" in unknown.output
    assert not (state / "gpu-slots" / "3").exists()
    bad = _gpu("cooldown", "../0", "--duration", "1h")
    assert bad.exit_code == 2 and "Not a GPU Slot value: ../0" in bad.output
    now = datetime.now(UTC)
    _hold(state, "3", now, now + timedelta(hours=1), now=now)
    listing = _gpu("ls")
    assert "gpu 3        orphaned" in listing.output
    lift = _gpu("cooldown", "3", "--clear")
    assert lift.exit_code == 0, lift.output
    assert "gpu 3: 1 cooldown(s) removed" in lift.output
    assert "orphaned" not in _gpu("ls").output
    for args in (
        ("cooldown", "0", "--clear", "--duration", "1h"),
        ("cooldown", "0", "--until", "14:00", "--duration", "1h"),
        ("cooldown", "0"),
        ("cooldown", "--duration", "1h"),
        ("cooldown", "0", "--all", "--duration", "1h"),
    ):
        assert _gpu(*args).exit_code == 2, args


def test_a_host_without_gpu_slots_has_no_gpu_slot_to_hold(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, slots=None)
    result = _gpu("cooldown", "0", "--duration", "1h")
    assert result.exit_code == 2
    assert "lists no [model_server] gpu_slots" in result.output
    assert "no GPU Slots" in _gpu("ls").output
