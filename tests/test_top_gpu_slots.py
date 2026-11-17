"""GPU Slots in the monitor: read from the lock table and ``nvidia-smi``, never by locking."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.model_server import GpuReading, claim_gpu_slot, gpu_slots
from silverquillm.monitor import Monitor, Stage
from silverquillm.monitor.gpus import GpuSlotStatus, gpu_slot_statuses
from silverquillm.monitor.headless import snapshot_document
from silverquillm.monitor.locks import held_locks

from .top_fixtures import NOW


def h100(index, used=14):
    return {
        "index": index,
        "uuid": f"GPU-{index}",
        "name": "NVIDIA H100 80GB HBM3",
        "memory_total_mib": 81559,
        "memory_used_mib": used,
        "power_limit_w": 700,
        "driver_version": "580.1",
    }


READING = GpuReading((h100(0), h100(1), h100(2, used=40000), h100(3)), frozenset({"GPU-3"}))


def served(run_id, slot, stage=Stage.RUNNING):
    return SimpleNamespace(run_id=run_id, model_server=True, gpu_slot=slot, stage=stage)


def lock_table_now(tmp_path):
    """A copy of the kernel lock table as it stands."""
    table = tmp_path / "proc-locks"
    table.write_text(Path("/proc/locks").read_text())
    return held_locks(table)


def test_each_slot_reads_held_busy_or_free_without_taking_its_lock(tmp_path):
    state = tmp_path / "state"
    slots = gpu_slots(state, ("0", "1", "2", "3"))
    claim = claim_gpu_slot(slots[:1], lambda: READING)
    held = lock_table_now(tmp_path)
    claim.release()
    runs = [
        served("grading-run", "0", Stage.GRADING),
        served("recording-run", "0", Stage.RECORDING),
        served("serving-run-0001", "0"),
    ]
    statuses = gpu_slot_statuses(state, ("0", "1", "2", "3"), held, READING, runs)
    assert [status.state for status in statuses] == ["held", "free", "busy", "busy"]
    assert statuses[0].run_id == "serving-run-0001"
    staging = gpu_slot_statuses(
        state,
        ("0",),
        held,
        READING,
        [served("grading-run", "0", Stage.GRADING), served("staging", "0", Stage.STARTING)],
    )
    assert staging[0].run_id == "staging"
    graded = gpu_slot_statuses(
        state, ("0",), held, READING, [served("grading-run", "0", Stage.GRADING)]
    )
    assert graded[0].state == "held" and graded[0].run_id is None
    assert (statuses[2].busy, statuses[3].busy) == ("memory_used", "compute_process")
    assert statuses[1].gpus == (h100(1),)
    # The monitor's read left every lock free for the next run to claim.
    claim_gpu_slot(slots, lambda: GpuReading(None)).release()


def test_an_unreadable_lock_table_or_nvidia_smi_reads_unknown_not_free(tmp_path):
    unread = GpuReading(None, reason="nvidia_smi_unavailable")
    claim_gpu_slot(gpu_slots(tmp_path, None), lambda: unread).release()
    (status,) = gpu_slot_statuses(tmp_path, None, None, unread, [])
    assert status == GpuSlotStatus(None, None, None, None, "nvidia_smi_unavailable", None)
    assert status.state == "unknown"


def monitor(tmp_path, config: str, reader):
    home = tmp_path / "config" / "silverquillm"
    home.mkdir(parents=True)
    (home / "config.toml").write_text(config)
    return Monitor(
        given={"state_root": tmp_path / "state", "runs_dir": tmp_path / "runs"},
        environ={"XDG_CONFIG_HOME": str(tmp_path / "config"), "SILVERQUILLM_HOST_LABEL": "luna"},
        docker=lambda: ([], None),
        clock=lambda: NOW,
        follow_output=False,
        gpu_reader=reader,
    )


def test_top_json_lists_the_hosts_gpu_slots(tmp_path):
    view = monitor(tmp_path, '[model_server]\ngpu_slots = ["0", "2"]\n', lambda: READING)
    try:
        document = snapshot_document(view.snapshot())
    finally:
        view.close()
    assert [slot["gpu_slot"] for slot in document["gpu_slots"]] == ["0", "2"]
    first, second = document["gpu_slots"]
    assert first["state"] == "free" and first["run_id"] is None
    assert first["gpus"] == [
        {
            "index": 0,
            "name": "NVIDIA H100 80GB HBM3",
            "uuid": "GPU-0",
            "memory_used_mib": 14,
            "memory_total_mib": 81559,
        }
    ]
    assert (second["state"], second["busy"]) == ("busy", "memory_used")


def test_a_host_without_a_local_model_server_never_runs_nvidia_smi(tmp_path):
    def unexpected():
        raise AssertionError("nvidia-smi read on a host with no model server")

    view = monitor(tmp_path, 'host_label = "plain"\n', unexpected)
    try:
        assert view.snapshot().gpu_slots == []
    finally:
        view.close()


def test_the_logins_pane_lists_each_gpu_slot_with_its_holder_and_why_it_is_busy():
    pytest.importorskip("textual")
    from silverquillm.top.dashboard import GpuSlotsPanel
    from silverquillm.top.theme import MTG

    from .test_top_cooldowns import _plain

    statuses = [
        GpuSlotStatus("0", True, None, (h100(0, used=30000),), None, "serving-run-0001"),
        GpuSlotStatus("1", False, None, (h100(1),)),
        GpuSlotStatus("2", False, "compute_process", (h100(2),)),
        GpuSlotStatus("3", False, None, None, "nvidia_smi_unavailable"),
    ]
    lines = _plain(GpuSlotsPanel.table(statuses, MTG)).splitlines()
    assert "GPU slots" in lines[0] and "2/4 free" in lines[0]
    assert "gpu 0" in lines[1] and "H100" in lines[1] and "held · serving-" in lines[1]
    assert "gpu 1" in lines[2] and lines[2].rstrip().endswith("free")
    assert "busy · another process" in lines[3]
    assert "nvidia_smi_unavailable" in lines[4]


def unusable_host(tmp_path):
    """Slots on a host whose nvidia-smi lists GPUs 0-2: one fine, one partly and one wholly
    missing, and one whose lock file this user cannot open."""
    state = tmp_path / "state"
    configured = ("0", "1,7", "8", "2")
    slots = gpu_slots(state, configured)
    claim_gpu_slot(slots[3:], lambda: GpuReading(None)).release()
    slots[3].lock_path.chmod(0)
    reading = GpuReading((h100(0), h100(1), h100(2)))
    return state, configured, slots, reading


def test_unusable_slots_read_unusable_with_the_reason_admission_gives(tmp_path):
    from silverquillm.karn.model_server import gpu_slot_availability

    state, configured, slots, reading = unusable_host(tmp_path)
    table = tmp_path / "proc-locks"
    table.write_text(Path("/proc/locks").read_text())
    try:
        statuses = gpu_slot_statuses(state, configured, held_locks(table), reading, [])
        assert [status.state for status in statuses] == ["free", "unusable", "unusable", "unusable"]
        claimable, unusable = gpu_slot_availability(slots, lambda: reading, locks=table)
        assert claimable
        assert tuple(status.unusable for status in statuses if status.unusable) == unusable
        assert statuses[1].unusable.startswith("gpu_slot_unknown_gpu:1,7")
        assert statuses[3].unusable.startswith("model_server_lock_unusable:")
        # An unread nvidia-smi alone never makes a slot unusable.
        unread = gpu_slot_statuses(state, ("7",), held_locks(table), GpuReading(None), [])
        assert unread[0].state == "free"
    finally:
        slots[3].lock_path.chmod(0o600)
    repaired = GpuReading((h100(0), h100(1), h100(2), h100(7), h100(8)))
    statuses = gpu_slot_statuses(state, configured, held_locks(table), repaired, [])
    assert [status.state for status in statuses] == ["free"] * 4
    assert gpu_slot_availability(slots, lambda: repaired, locks=table) == (True, ())


def test_a_held_slot_reads_held_whatever_else_is_true(tmp_path):
    state = tmp_path / "state"
    slots = gpu_slots(state, ("7",))
    claim = claim_gpu_slot(slots, lambda: GpuReading(None))
    held = lock_table_now(tmp_path)
    claim.release()
    missing = GpuReading((h100(0),))
    (status,) = gpu_slot_statuses(state, ("7",), held, missing, [served("run", "7")])
    assert status.state == "held" and status.unusable is not None


def test_top_json_and_the_pane_show_unusable_slots_and_count_them_out_of_free(tmp_path):
    pytest.importorskip("textual")
    from silverquillm.top.dashboard import GpuSlotsPanel
    from silverquillm.top.theme import MTG

    from .test_top_cooldowns import _plain

    _, configured, slots, reading = unusable_host(tmp_path)
    try:
        view = monitor(
            tmp_path,
            f"[model_server]\ngpu_slots = {list(configured)!r}\n".replace("'", '"'),
            lambda: reading,
        )
        try:
            snapshot = view.snapshot()
        finally:
            view.close()
        document = snapshot_document(snapshot)
        rows = {row["gpu_slot"]: row for row in document["gpu_slots"]}
        assert rows["0"]["state"] == "free" and rows["0"]["unusable"] is None
        for value in ("1,7", "8", "2"):
            assert rows[value]["state"] == "unusable" and rows[value]["unusable"]
        lines = _plain(GpuSlotsPanel.table(snapshot.gpu_slots, MTG)).splitlines()
        assert "1/4 free" in lines[0]
        assert "unusable · gpu_slot_unknown_gpu:1,7" in lines[2]
        assert "unusable · model_server_lock_unusable" in lines[4]
    finally:
        slots[3].lock_path.chmod(0o600)
