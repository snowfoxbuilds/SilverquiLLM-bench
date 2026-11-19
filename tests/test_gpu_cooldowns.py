"""GPU Slot Cooldown Schedules: claims, the scheduler's hint, the monitor, and `gpu` commands."""

from __future__ import annotations

import contextlib
import fcntl
import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn.cooldowns import (
    COOLDOWNS_FILE,
    EXTENSION_STEP,
    add_cooldown,
    cooldown,
    edited,
    extended,
    held_until,
    read_schedule,
)
from silverquillm.karn.definition import KarnError
from silverquillm.karn.model_server import (
    GpuReading,
    ModelServerBusyError,
    claim_gpu_slot,
    extend_gpu_cooldowns,
    gpu_schedule_dir,
    gpu_slot_availability,
    gpu_slots,
    writable_gpu_schedule_dir,
)
from silverquillm.karn.model_server import read_gpus as _real_read_gpus
from silverquillm.monitor.gpus import GpuSlotStatus, gpu_slot_statuses, orphaned_gpu_schedules
from silverquillm.monitor.headless import snapshot_document
from silverquillm.monitor.locks import lock_held, lock_holders

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


def test_a_claim_rechecks_the_cooldown_once_it_holds_the_lock(tmp_path, monkeypatch):
    from silverquillm.karn import model_server

    now = datetime.now(UTC)
    slots = gpu_slots(tmp_path, ("0", "1"))
    real_lock = model_server._lock

    def lock_after_a_cooldown_lands(slot):
        if slot.value == "0":
            _hold(tmp_path, "0", now, now + timedelta(hours=1), now=now)
        return real_lock(slot)

    monkeypatch.setattr(model_server, "_lock", lock_after_a_cooldown_lands)
    claim = claim_gpu_slot(slots, _free)
    assert claim.slot.value == "1"
    # The passed-over slot's lock was let go, not leaked.
    assert lock_held(slots[0].lock_path, lock_table_now(tmp_path)) is False
    claim.release()
    monkeypatch.setattr(model_server, "_lock", real_lock)
    with pytest.raises(ModelServerBusyError):
        claim_gpu_slot(slots[:1], _free)


def test_a_gpu_cooldown_of_any_scope_holds_the_slot_for_the_claim_hint_and_monitor(tmp_path):
    now = datetime.now(UTC)
    slots = gpu_slots(tmp_path, ("0",))
    window = cooldown(now, now + timedelta(hours=1), now=now, scope="fable")
    add_cooldown(writable_gpu_schedule_dir(tmp_path, "0"), window, now=now)
    assert slots[0].cooling_until(now) == window.end
    with pytest.raises(ModelServerBusyError):
        claim_gpu_slot(slots, _free)
    assert not gpu_slot_availability(slots, _free, tmp_path / "no-locks")[0]
    (status,) = gpu_slot_statuses(tmp_path, ("0",), lock_table_now(tmp_path), _free(), [])
    assert status.state == "cooldown" and status.cooldown_until == window.end


def test_a_schedule_reached_through_a_symlink_or_a_non_directory_holds_nothing(tmp_path):
    now = datetime.now(UTC)
    elsewhere = tmp_path / "elsewhere"
    _hold(elsewhere, "0", now, now + timedelta(hours=1), now=now)
    _hold(elsewhere, "3", now, now + timedelta(hours=1), now=now)
    linked_slot = tmp_path / "linked-slot"
    (linked_slot / "gpu-slots").mkdir(parents=True)
    (linked_slot / "gpu-slots" / "0").symlink_to(elsewhere / "gpu-slots" / "0")
    linked_root = tmp_path / "linked-root"
    linked_root.mkdir()
    (linked_root / "gpu-slots").symlink_to(elsewhere / "gpu-slots")
    a_file = tmp_path / "a-file"
    a_file.mkdir()
    (a_file / "gpu-slots").write_text("")
    for state in (linked_slot, linked_root, a_file):
        slots = gpu_slots(state, ("0",))
        assert slots[0].cooling_until(now) is None, state
        claim_gpu_slot(slots, _free).release()
        assert gpu_slot_availability(slots, _free, tmp_path / "no-locks")[0], state
        (status,) = gpu_slot_statuses(state, ("0",), lock_table_now(tmp_path), _free(), [])
        assert status.state == "free" and status.cooldowns == (), state
        assert orphaned_gpu_schedules(state, None) == [], state


def test_gpu_cooldown_all_clear_on_a_host_without_gpu_slots_points_at_the_orphans(
    tmp_path, monkeypatch
):
    state = _configure(tmp_path, monkeypatch, slots=None)
    now = datetime.now(UTC)
    _hold(state, "1", now, now + timedelta(hours=1), now=now)
    result = _gpu("cooldown", "--all", "--clear")
    assert result.exit_code == 2
    assert "lists no [model_server] gpu_slots" in result.output
    assert "gpu cooldown <value> --clear" in result.output
    assert len(read_schedule(gpu_schedule_dir(state, "1"))) == 1


# A GPU Cooldown extended while the GPU is used outside the bench (grilling 2026-11-19).


def _extending(state, value, start, end, *, now, note=None, extend=True):
    window = cooldown(start, end, now=now, note=note, extend=extend)
    return add_cooldown(writable_gpu_schedule_dir(state, value), window, now=now)


def _used_by(pid, used=14_000):
    """A reading as nvidia-smi gives it: GPU 0 running the compute process ``pid``."""
    from .test_karn_model_server import smi_output

    return _real_read_gpus(
        smi_output(
            b"0, GPU-0, NVIDIA H100 80GB HBM3, %d, 81559, 700.00, 580.1\n"
            b"1, GPU-1, NVIDIA H100 80GB HBM3, 14, 81559, 700.00, 580.1\n" % used,
            b"GPU-0, %d, %d\n" % (pid, used),
        )
    )


def _memory_only(used=14_000):
    """GPU 0's memory in use by a job no visible compute process explains."""
    return GpuReading((h100(0, used=used), h100(1)))


def _schedule(state, value="0", now=None):
    from silverquillm.karn.cooldowns import _read

    return _read(gpu_schedule_dir(state, value), now or datetime.now(UTC))


@contextlib.contextmanager
def _holding(slot):
    """The slot's lock held by this process, as a run's claim holds it."""
    slot.lock_path.parent.mkdir(parents=True, exist_ok=True)
    with slot.lock_path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def test_compute_processes_are_read_with_their_pids():
    reading = _used_by(4242)
    assert reading.compute_pids == (("GPU-0", 4242),)
    assert reading.compute_uuids == {"GPU-0"}


def test_an_ending_cooldown_is_extended_while_another_job_uses_the_gpu(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0", "1"))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ("0",)
    (after,) = _schedule(tmp_path)
    assert after.end == window.end + EXTENSION_STEP and after.extensions == 1
    assert after.start == window.start and after.extend


def test_a_claim_extends_the_cooldown_it_finds_ending_and_passes_the_slot_over(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0", "1"))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    claim = claim_gpu_slot(slots, lambda: _used_by(4242), now=now)
    assert claim.slot.value == "1"
    claim.release()
    assert _schedule(tmp_path)[0].end == window.end + EXTENSION_STEP


def test_another_users_job_extends_a_cooldown_even_while_a_run_holds_the_slot(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    with _holding(slots[0]):
        # PID 1 descends from no run: it is work outside the bench.
        assert extend_gpu_cooldowns(slots, reading=_used_by(1), now=now) == ("0",)


def test_the_benchs_own_server_never_extends_a_cooldown(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    server = subprocess.Popen(["sleep", "30"])
    try:
        with _holding(slots[0]):
            # The run holding the lock, and the server it started below it.
            for pid in (os.getpid(), server.pid):
                assert extend_gpu_cooldowns(slots, reading=_used_by(pid), now=now) == ()
    finally:
        server.kill()
        server.wait()
    assert _schedule(tmp_path) == [window]


def test_unexplained_memory_extends_only_while_no_run_holds_the_slot(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    with _holding(slots[0]):
        assert extend_gpu_cooldowns(slots, reading=_memory_only(), now=now) == ()
    assert extend_gpu_cooldowns(slots, reading=_memory_only(), now=now) == ("0",)


def test_a_late_check_moves_the_end_on_one_step_from_where_it_was(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    ended = now - timedelta(minutes=20)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", ended - timedelta(hours=1), ended, now=ended - timedelta(minutes=1))
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ("0",)
    (after,) = _schedule(tmp_path)
    assert after.end == ended + EXTENSION_STEP and after.extensions == 1
    assert after.in_force(now)


def _recorded(state, value, *windows):
    """Write ``windows`` as the slot's schedule, ended ones included, as a schedule last
    written before they ended holds them."""
    from silverquillm.karn.cooldowns import edit_schedule

    earliest = min(window.start for window in windows)
    edit_schedule(writable_gpu_schedule_dir(state, value), lambda _: list(windows), now=earliest)
    return list(windows)


@pytest.mark.parametrize(
    "late", [EXTENSION_STEP, timedelta(minutes=95), timedelta(days=30)], ids=str
)
def test_a_cooldown_ended_a_step_or_more_ago_is_never_revived(tmp_path, late):
    now = datetime.now(UTC).replace(microsecond=0)
    ended = now - late
    slots = gpu_slots(tmp_path, ("0",))
    window = cooldown(ended - timedelta(days=1), ended, now=ended - timedelta(days=1), extend=True)
    _recorded(tmp_path, "0", window)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == [window]


def test_a_free_check_after_the_end_records_the_lapse(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    ended = now - timedelta(minutes=2)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", ended - timedelta(hours=2), ended, now=ended - timedelta(hours=1))
    lapsed = ended + timedelta(seconds=10)
    assert extend_gpu_cooldowns(slots, reading=_free(), now=lapsed) == ()
    assert _schedule(tmp_path, now=lapsed) == []
    # Work outside the bench starting a minute later finds nothing to revive.
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == []


@pytest.mark.parametrize("earlier", [timedelta(days=1), timedelta(minutes=20)], ids=str)
def test_a_no_extend_cooldown_is_never_extended_through_an_earlier_ended_one(tmp_path, earlier):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    first = cooldown(
        now - earlier - timedelta(hours=1), now - earlier, now=now - timedelta(days=2), extend=True
    )
    second = cooldown(
        now - timedelta(minutes=10),
        now - timedelta(minutes=5),
        now=now - timedelta(days=2),
        note="no-extend",
    )
    windows = _recorded(tmp_path, "0", first, second)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == windows


def test_a_long_ended_cooldown_never_extends_one_in_force(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    stale = cooldown(
        now - timedelta(days=8), now - timedelta(days=7), now=now - timedelta(days=9), extend=True
    )
    night = cooldown(
        now - timedelta(hours=1), now + timedelta(hours=3), now=now - timedelta(days=3), note="n"
    )
    _recorded(tmp_path, "0", stale, night)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert night in _schedule(tmp_path) and night.extensions == 0


def test_nvidia_smi_is_not_read_on_every_pass_for_an_ended_cooldown(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0", "1"))
    stale = now - timedelta(days=30)
    window = cooldown(
        stale - timedelta(hours=1), stale, now=stale - timedelta(hours=1), extend=True
    )
    _recorded(tmp_path, "0", window)
    ended = now - timedelta(minutes=1)
    _extending(tmp_path, "1", ended - timedelta(hours=1), ended, now=ended - timedelta(minutes=1))
    reads = []

    def read():
        reads.append(1)
        return _free()

    for _ in range(3):
        assert extend_gpu_cooldowns(slots, read, now=now) == ()
    # Once, for the window that just ended; that check records its lapse.
    assert reads == [1]


def test_a_run_releasing_the_slot_while_nvidia_smi_is_read_still_counts_as_the_bench(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    slots[0].lock_path.parent.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(["sleep", "30"])
    handle = slots[0].lock_path.open("a")
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def read_as_the_run_ends():
        seen = _used_by(server.pid)
        handle.close()
        return seen

    try:
        assert extend_gpu_cooldowns(slots, read_as_the_run_ends, now=now) == ()
    finally:
        handle.close()
        server.kill()
        server.wait()
    assert _schedule(tmp_path) == [window]


def test_nothing_is_extended_when_the_lock_table_cannot_be_read(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    slots[0].lock_path.touch()
    missing = tmp_path / "no-locks"
    assert lock_holders(slots[0].lock_path, missing) is None
    assert extend_gpu_cooldowns(slots, None, missing, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == [window]


def test_nothing_is_extended_while_a_holder_the_lock_table_omits_holds_the_slot(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    empty = tmp_path / "locks"
    empty.write_text("")
    with _holding(slots[0]):
        assert extend_gpu_cooldowns(slots, None, empty, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == [window]
    # With the lock truly free, the probe takes it only for an instant.
    assert extend_gpu_cooldowns(slots, None, empty, reading=_used_by(4242), now=now) == ("0",)
    with _holding(slots[0]):
        pass


def test_an_edited_cooldown_never_extends():
    now = datetime.now(UTC).replace(microsecond=0)
    window = cooldown(
        now - timedelta(hours=1),
        now + timedelta(seconds=30),
        now=now - timedelta(hours=1),
        extend=True,
    )
    assert extended([window], now) is not None
    for change in ({}, {"end": now + timedelta(seconds=20)}, {"note": "moved"}):
        pulled = edited(window, **change)
        assert not pulled.extend and pulled.start == window.start
        assert pulled == replace(window, **change, extend=False)
        assert extended([pulled], now) is None


def test_each_check_as_the_end_nears_extends_it_again(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now)
    # Nothing is due until the new end nears.
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now + timedelta(minutes=5)) == ()
    later = window.end + EXTENSION_STEP - timedelta(seconds=20)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=later) == ("0",)
    (after,) = _schedule(tmp_path, now=later)
    assert after.end == window.end + 2 * EXTENSION_STEP and after.extensions == 2


def test_a_cooldown_lapses_once_the_gpu_is_free(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    assert extend_gpu_cooldowns(slots, reading=_free(), now=now) == ()
    assert _schedule(tmp_path) == [window]
    claim_gpu_slot(slots, _free, now=window.end).release()


def test_an_extension_reaching_the_next_cooldown_merges_the_two(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    first = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    second = _extending(
        tmp_path, "0", now + timedelta(minutes=20), now + timedelta(hours=3), now=now, note="night"
    )
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ("0",)
    (merged,) = _schedule(tmp_path)
    assert (merged.start, merged.end, merged.note) == (first.start, second.end, "night")
    assert merged.extend and merged.extensions == 1


def test_a_merge_keeps_whether_the_later_cooldown_extends(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    _extending(
        tmp_path, "0", now + timedelta(minutes=20), now + timedelta(hours=1), now=now, extend=False
    )
    extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now)
    (merged,) = _schedule(tmp_path)
    assert not merged.extend
    ending = merged.end - timedelta(seconds=20)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=ending) == ()


def test_a_cooldown_covered_by_another_is_not_ending(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    _extending(tmp_path, "0", now - timedelta(minutes=10), now + timedelta(hours=2), now=now)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()


def test_an_edited_or_no_extend_cooldown_ends_on_time(tmp_path):
    from silverquillm.karn.cooldowns import edit_schedule

    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(hours=2), now=now)
    directory = gpu_schedule_dir(tmp_path, "0")
    pulled = edited(window, end=now + timedelta(seconds=30))
    edit_schedule(directory, lambda cooldowns: [pulled], now=now)
    assert not pulled.extend
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == [pulled]
    _extending(
        tmp_path, "1", now - timedelta(hours=1), now + timedelta(seconds=30), now=now, extend=False
    )
    assert extend_gpu_cooldowns(gpu_slots(tmp_path, ("1",)), reading=_used_by(4242), now=now) == ()


def test_an_extension_never_reaches_past_the_horizon(tmp_path, monkeypatch):
    from silverquillm.karn import cooldowns

    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0",))
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    monkeypatch.setattr(cooldowns, "HORIZON", timedelta(minutes=10))
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    assert _schedule(tmp_path) == [window]


def test_a_failed_extension_fails_neither_a_claim_nor_a_scheduler_pass(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from silverquillm.karn import model_server
    from silverquillm.karn.batching import KarnScheduler
    from silverquillm.karn.model_server import ModelServerHost

    now = datetime.now(UTC).replace(microsecond=0)
    slots = gpu_slots(tmp_path, ("0", "1"))
    _extending(tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)

    def refused(*_, **__):
        raise KarnError("cooldown_schedule_busy")

    monkeypatch.setattr(model_server, "extend_ending", refused)
    assert extend_gpu_cooldowns(slots, reading=_used_by(4242), now=now) == ()
    claim = claim_gpu_slot(slots, lambda: _used_by(4242), now=now)
    assert claim.slot.value == "1"
    claim.release()
    scheduler = SimpleNamespace(
        model_server_host=ModelServerHost(gpu_slots=("0", "1")),
        options={"state_root": tmp_path},
        gpu_reader=lambda: _used_by(4242),
    )
    KarnScheduler._extend_gpu_cooldowns(scheduler)


def test_a_scheduler_pass_extends_an_ending_cooldown(tmp_path):
    from types import SimpleNamespace

    from silverquillm.karn.batching import KarnScheduler
    from silverquillm.karn.model_server import ModelServerHost

    now = datetime.now(UTC).replace(microsecond=0)
    window = _extending(
        tmp_path, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now
    )
    reads = []
    scheduler = SimpleNamespace(
        model_server_host=ModelServerHost(gpu_slots=("0", "1")),
        options={"state_root": tmp_path},
        gpu_reader=lambda: reads.append(1) or _used_by(4242),
    )
    KarnScheduler._extend_gpu_cooldowns(scheduler)
    assert _schedule(tmp_path)[0].end == window.end + EXTENSION_STEP
    # Nothing ending: nvidia-smi is not read at all.
    KarnScheduler._extend_gpu_cooldowns(scheduler)
    assert reads == [1]


def test_gpu_ls_and_top_json_show_how_often_a_cooldown_was_extended(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    now = datetime.now(UTC).replace(microsecond=0)
    _extending(state, "0", now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    extend_gpu_cooldowns(gpu_slots(state, ("0",)), reading=_used_by(4242), now=now)
    listed = _gpu("ls")
    assert listed.exit_code == 0, listed.output
    assert "(busy +1)" in listed.output
    held = lock_table_now(tmp_path)
    (status,) = gpu_slot_statuses(state, ("0",), held, _free(), [])
    assert status.state == "cooldown" and status.cooldown_extensions == 1
    document = snapshot_document_gpu(status)
    assert document["cooldown_extensions"] == 1
    assert document["cooldowns"][0]["extensions"] == 1 and document["cooldowns"][0]["extend"]


def snapshot_document_gpu(status):
    from silverquillm.monitor.headless import _gpu_slot

    return _gpu_slot(status)


def test_gpu_cooldown_extends_unless_told_not_to(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    assert _gpu("cooldown", "0", "--duration", "2h").exit_code == 0
    assert _gpu("cooldown", "1", "--duration", "2h", "--no-extend").exit_code == 0
    assert [c.extend for c in _schedule(state, "0")] == [True]
    assert [c.extend for c in _schedule(state, "1")] == [False]
    listed = _gpu("ls")
    assert "no-extend" in listed.output.split("gpu 1")[1]
    refused = _gpu("cooldown", "1", "--clear", "--no-extend")
    assert refused.exit_code == 2


def test_a_login_profiles_cooldowns_are_never_extended(tmp_path):
    now = datetime.now(UTC).replace(microsecond=0)
    window = cooldown(now - timedelta(hours=1), now + timedelta(seconds=30), now=now)
    assert not window.extend and "extend" not in window.document()
    assert "extensions" not in window.document()
