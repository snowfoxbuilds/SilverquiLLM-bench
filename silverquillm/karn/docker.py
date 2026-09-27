"""Docker lifecycle and enforced per-run HTTPS egress for Karn candidates."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .definition import KarnError, inspect_image, strict_json

RUN_LABEL = "org.silverquillm.run"


def redacted_tail(payload: bytes, maximum: int, redactions) -> bytes:
    """Keep at most *maximum* bytes of the tail, redacting before the cut.

    *payload* carries a margin of the longest secret's length, so a secret straddling the
    retention boundary is wholly visible here; the cut moves past it rather than keeping
    its suffix as an unredacted fragment.
    """
    cut, moved = max(0, len(payload) - maximum), True
    while moved:
        moved = False
        for secret in redactions:
            start = payload.find(secret, max(0, cut - len(secret) + 1))
            if start != -1 and start < cut:
                cut, moved = start + len(secret), True
    tail = payload[cut:]
    for secret in sorted(redactions, key=len, reverse=True):
        tail = tail.replace(secret, b"[REDACTED]")
    return tail[-maximum:] if maximum else b""


class Docker:
    def command(self, *arguments: str, timeout: float = 30, check: bool = True):
        try:
            result = subprocess.run(
                ["docker", *arguments], capture_output=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            raise KarnError("docker_command_failed:" + arguments[0]) from None
        if check and result.returncode:
            raise KarnError("docker_command_failed:" + arguments[0])
        return result

    def inspect_image(self, reference: str) -> dict:
        return inspect_image(reference)

    def inspect_container(self, name: str) -> dict | None:
        result = self.command("container", "inspect", name, check=False)
        if result.returncode:
            if b"No such container" in result.stderr or b"No such object" in result.stderr:
                return None
            raise KarnError("container_inspection_failed")
        rows = strict_json(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise KarnError("invalid_container_inspection")
        return rows[0]

    def stop_and_confirm(self, name: str, run_id: str) -> None:
        info = self.inspect_container(name)
        if info is None:
            return
        if info.get("Config", {}).get("Labels", {}).get(RUN_LABEL) != run_id:
            raise KarnError("container_recovery_identity_mismatch")
        if info["State"].get("Running"):
            self.command("kill", name, check=False)
        deadline = time.monotonic() + 30
        while True:
            info = self.inspect_container(name)
            if info is None or not info["State"].get("Running"):
                return
            if time.monotonic() >= deadline:
                raise KarnError("container_stop_unconfirmed")
            time.sleep(0.05)

    def cleanup_run(self, container_name: str, run_id: str) -> None:
        """Remove only this run's owned workload, proxy, and isolated network after harvest."""
        for name in (container_name, "sq-proxy-" + run_id):
            if self.inspect_container(name) is not None:
                self.stop_and_confirm(name, run_id)
                self.remove(name)
        network = "sq-net-" + run_id
        inspection = self.command("network", "inspect", network, check=False)
        if inspection.returncode:
            if b"No such network" in inspection.stderr or b"not found" in inspection.stderr:
                return
            raise KarnError("network_recovery_inspection_failed")
        rows = strict_json(inspection.stdout)
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or rows[0].get("Labels", {}).get(RUN_LABEL) != run_id
        ):
            raise KarnError("network_recovery_identity_mismatch")
        self.command("network", "rm", network)

    def remove(self, name: str) -> None:
        self.command("rm", "-f", name, check=False)

    def logs(self, name: str, stdout: Path, stderr: Path, limits: dict, *, redactions=()) -> None:
        process = subprocess.Popen(
            ["docker", "logs", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        failures = []
        margin = max((len(secret) for secret in redactions), default=0)

        def retain_tail(stream, target, maximum):
            chunks, size = deque(), 0
            try:
                while chunk := stream.read(65536):
                    chunks.append(chunk)
                    size += len(chunk)
                    while size > maximum + margin and chunks:
                        excess = size - maximum - margin
                        first = chunks.popleft()
                        if len(first) > excess:
                            chunks.appendleft(first[excess:])
                            size -= excess
                        else:
                            size -= len(first)
                target.write_bytes(redacted_tail(b"".join(chunks), maximum, redactions))
            except OSError:
                failures.append("log_retention_failed")
            finally:
                stream.close()

        threads = [
            threading.Thread(target=retain_tail, args=(stream, path, limits[key]["max_bytes"]))
            for key, stream, path in (
                ("stdout", process.stdout, stdout),
                ("stderr", process.stderr, stderr),
            )
        ]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            failures.append("container_logs_timeout")
        finally:
            for thread in threads:
                thread.join()
        if process.returncode or failures:
            raise KarnError(failures[0] if failures else "container_logs_unavailable")


@dataclass
class Network:
    docker: Docker
    run_id: str
    policy: dict
    image_id: str
    directory: Path
    collector_endpoint: str | None = None
    telemetry_endpoint: str | None = None
    network: str = "none"
    proxy_name: str | None = None
    environment: dict | None = None

    def __enter__(self):
        self.environment = {}
        self.telemetry_endpoint = self.collector_endpoint
        if self.policy["mode"] == "none":
            return self
        if self.policy["mode"] == "open":
            self.network = "bridge"
            return self
        self.network = "sq-net-" + self.run_id
        self.proxy_name = "sq-proxy-" + self.run_id
        try:
            self.docker.command(
                "network",
                "create",
                "--internal",
                "--label",
                RUN_LABEL + "=" + self.run_id,
                "--opt",
                "com.docker.network.bridge.gateway_mode_ipv4=isolated",
                self.network,
            )
            arguments = [
                "create",
                "--pull",
                "never",
                "--name",
                self.proxy_name,
                "--label",
                RUN_LABEL + "=" + self.run_id,
                "--network",
                "bridge",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "128",
                "--memory",
                "128m",
                "--cpus",
                "1",
                "--env",
                "SILVERQUILLM_HTTPS_HOSTS=" + json.dumps(self.policy["https_hosts"]),
                "--mount",
                f"type=bind,src={Path(__file__).with_name('proxy.py')},dst=/proxy.py,readonly",
                "--entrypoint",
                "python3",
                self.image_id,
                "-I",
                "/proxy.py",
            ]
            if self.collector_endpoint:
                arguments[1:1] = ["--env", "SILVERQUILLM_OTLP_ENDPOINT=" + self.collector_endpoint]
            self.docker.command(*arguments)
            self.docker.command("network", "connect", self.network, self.proxy_name)
            self.docker.command("start", self.proxy_name)
            deadline = time.monotonic() + 15
            while True:
                result = self.docker.command(
                    "exec",
                    self.proxy_name,
                    "python3",
                    "-I",
                    "-c",
                    "import socket; socket.create_connection(('127.0.0.1',3128),1).close()",
                    check=False,
                )
                if result.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise KarnError("network_proxy_not_ready")
                time.sleep(0.1)
            info = self.docker.inspect_container(self.proxy_name)
            address = info["NetworkSettings"]["Networks"][self.network]["IPAddress"]
            endpoint = "http://" + address + ":3128"
            if self.collector_endpoint:
                self.telemetry_endpoint = endpoint + "/v1/logs"
            self.environment = {
                key: endpoint for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
            }
            self.environment.update(
                NO_PROXY="localhost,127.0.0.1," + address, no_proxy="localhost,127.0.0.1," + address
            )
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self.proxy_name is not None:
            with contextlib.suppress(KarnError):
                self.docker.remove(self.proxy_name)
        if self.network not in ("none", "bridge"):
            with contextlib.suppress(KarnError):
                self.docker.command("network", "rm", self.network, check=False)
