"""Small CONNECT-only proxy run inside the per-run network sidecar."""

from __future__ import annotations

import ipaddress
import json
import os
import select
import socket
import socketserver
import threading
import urllib.parse
import urllib.request


def read_exactly(source, length: int) -> bytes:
    """The handlers read an unbuffered socket, where one read may return part of a body."""
    parts, remaining = [], length
    while remaining:
        part = source.read(remaining)
        if not part:
            break
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def resolve_public(host: str, port: int) -> list[tuple]:
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("nonpublic_destination")
    return addresses


class ConnectProxy(socketserver.StreamRequestHandler):
    rbufsize = 0

    def handle(self):
        self.connection.settimeout(30)
        remote = None
        try:
            first = self.rfile.readline(8193)
            if len(first) > 8192:
                raise ValueError("request_too_large")
            method, authority, version = first.decode("ascii").strip().split(" ")
            if method == "POST" and authority == "/v1/logs" and self.server.collector_endpoint:
                self.forward_telemetry()
                return
            host, port = authority.rsplit(":", 1)
            if method != "CONNECT" or version not in ("HTTP/1.0", "HTTP/1.1") or port != "443":
                raise ValueError("connect_https_required")
            if host not in self.server.allowed_hosts:
                raise ValueError("host_not_allowed")
            remaining = 32768
            while True:
                header = self.rfile.readline(min(8193, remaining + 1))
                remaining -= len(header)
                if not header or remaining < 0 or len(header) > 8192:
                    raise ValueError("invalid_headers")
                if header in (b"\r\n", b"\n"):
                    break
            for family, kind, protocol, _, address in resolve_public(host, 443):
                remote = socket.socket(family, kind, protocol)
                remote.settimeout(30)
                try:
                    remote.connect(address)
                    break
                except OSError:
                    remote.close()
                    remote = None
            if remote is None:
                raise OSError("destination_unavailable")
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            while True:
                readers, _, _ = select.select([self.connection, remote], [], [], 120)
                if not readers:
                    return
                for reader in readers:
                    data = reader.recv(65536)
                    if not data:
                        return
                    (remote if reader is self.connection else self.connection).sendall(data)
        except (OSError, ValueError, UnicodeError):
            try:
                self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            if remote is not None:
                remote.close()

    def forward_telemetry(self):
        headers = {}
        remaining = 32768
        while True:
            line = self.rfile.readline(8193)
            remaining -= len(line)
            if not line or len(line) > 8192 or remaining < 0:
                raise ValueError("invalid_headers")
            if line in (b"\r\n", b"\n"):
                break
            key, value = line.decode("ascii").split(":", 1)
            headers[key.lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        if (
            not 0 < length <= 16 * 1024 * 1024
            or headers.get("content-type", "").split(";")[0] != "application/json"
        ):
            raise ValueError("invalid_otlp_request")
        body = read_exactly(self.rfile, length)
        if len(body) != length:
            raise ValueError("incomplete_otlp_request")
        request = urllib.request.Request(
            self.server.collector_endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            payload = response.read(1024 * 1024)
        self.wfile.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(payload)).encode()
            + b"\r\n\r\n"
            + payload
        )


class ModelForward(socketserver.StreamRequestHandler):
    """The workload's plain-HTTP route to the host's model relay: one request per connection,
    only under ``/v1/``, and only to the one relay address the host gave the sidecar."""

    rbufsize = 0

    def handle(self):
        # Prompt processing at a long context can keep the first byte away for many minutes.
        self.connection.settimeout(1800)
        remote = None
        try:
            first = self.rfile.readline(8193)
            if len(first) > 8192:
                raise ValueError("request_too_large")
            method, target, version = first.decode("ascii").strip().split(" ")
            if (
                method not in ("GET", "POST")
                or version not in ("HTTP/1.0", "HTTP/1.1")
                or not target.startswith("/v1/")
                or any(c in target for c in "\\ ?#")
                or ".." in target
            ):
                raise ValueError("model_request_refused")
            headers, remaining = {}, 32768
            while True:
                line = self.rfile.readline(min(8193, remaining + 1))
                remaining -= len(line)
                if not line or remaining < 0 or len(line) > 8192:
                    raise ValueError("invalid_headers")
                if line in (b"\r\n", b"\n"):
                    break
                key, value = line.decode("ascii").split(":", 1)
                headers[key.strip().lower()] = value.strip()
            if "transfer-encoding" in headers:
                raise ValueError("chunked_request_refused")
            length = int(headers.get("content-length", "0"))
            if not 0 <= length <= 64 * 1024 * 1024:
                raise ValueError("model_request_too_large")
            body = read_exactly(self.rfile, length)
            if len(body) != length:
                raise ValueError("incomplete_model_request")
            relay = urllib.parse.urlsplit(self.server.model_endpoint)
            remote = socket.create_connection((relay.hostname, relay.port), timeout=1800)
            head = (
                f"{method} {relay.path}{target} HTTP/1.1\r\nHost: {relay.netloc}\r\n"
                f"Content-Type: application/json\r\nContent-Length: {length}\r\n"
                "Connection: close\r\n\r\n"
            )
            remote.sendall(head.encode("ascii") + body)
            while data := remote.recv(65536):
                self.connection.sendall(data)
        except (OSError, ValueError, UnicodeError):
            try:
                self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            if remote is not None:
                remote.close()


class ModelForwardServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, model_endpoint):
        self.model_endpoint = model_endpoint
        super().__init__(address, ModelForward)


class ProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, allowed_hosts, collector_endpoint=None):
        self.collector_endpoint = collector_endpoint
        self.allowed_hosts = frozenset(allowed_hosts)
        super().__init__(address, ConnectProxy)


if __name__ == "__main__":
    hosts = json.loads(os.environ["SILVERQUILLM_HTTPS_HOSTS"])
    if os.environ.get("SILVERQUILLM_MODEL_ENDPOINT"):
        forward = ModelForwardServer(("0.0.0.0", 8080), os.environ["SILVERQUILLM_MODEL_ENDPOINT"])
        threading.Thread(target=forward.serve_forever, daemon=True).start()
    with ProxyServer(
        ("0.0.0.0", 3128), hosts, os.environ.get("SILVERQUILLM_OTLP_ENDPOINT")
    ) as server:
        server.serve_forever()
