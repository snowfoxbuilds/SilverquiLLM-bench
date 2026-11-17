"""GPU Slots in the monitor: read from the lock table and ``nvidia-smi``, never by locking."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.model_server import GpuReading, claim_gpu_slot, gpu_slots
from silverquillm.monitor import Monitor
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


def served(run_id, slot, *, running=True):
    return SimpleNamespace(
        run_id=run_id,
        model_server=True,
        gpu_slot=slot,
        container=SimpleNamespace(running=running),
    )


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
    runs = [served("graded-run", "0", running=False), served("serving-run-0001", "0")]
    statuses = gpu_slot_statuses(state, ("0", "1", "2", "3"), held, READING, runs)
    assert [status.state for status in statuses] == ["held", "free", "busy", "busy"]
    assert statuses[0].run_id == "serving-run-0001"
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
