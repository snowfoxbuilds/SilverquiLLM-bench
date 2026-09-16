"""Build explicit real CLI references from pinned public artifacts; never runs inference."""

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import uuid
from pathlib import Path

from karn import bootstrap, initializer
from karn.definition import canonical, new_definition

ROOT = Path(__file__).resolve().parent


def definition(adapter, image, lock):
    doc = new_definition(
        name="vanilla-" + adapter + "-standalone",
        mode="automaton",
        image=image,
        main=["python3", "/opt/benchmark/adapter.py", adapter],
        definition_version=3,
    ).document
    doc["definition_id"] = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "silverquillm:vanilla:" + adapter + ":" + image)
    )
    runtime = doc["runtime"]
    runtime["environment"] = {
        "BENCHMARK_MODEL": lock["native"][adapter]["model"],
        "DISABLE_AUTOUPDATER": "1",
    }
    runtime["network"]["mode"] = "open"
    runtime["bootstrap"] = {
        "argv": ["python3", "/opt/benchmark/bootstrap.py"],
        "protocol": "identity-v2",
        "identity_input": "/input/identity.json",
        "handoff": "/output/identity.json",
        "home": "/home/construct",
        "shell": "/bin/sh",
    }
    runtime["mounts"] = [
        {
            "name": name,
            "target": "/" + name,
            "source": {"kind": "runtime", "value": name},
            "persistent": False,
            "purpose": name,
            "access": "read_only" if name == "input" else "read_write",
        }
        for name in ("workspace", "input", "output")
    ]
    runtime["files"] = [
        {"name": name, "mount": mount, "path": path, "direction": direction, "schema": schema}
        for name, mount, path, direction, schema in [
            ("prompt", "input", "prompt.md", "input", {"type": "string"}),
            ("request", "input", "request.json", "input", {"type": "object"}),
            ("identity", "input", "identity.json", "input", {"type": "object"}),
            ("handoff", "output", "identity.json", "status", {"type": "object"}),
            ("proposal", "output", "proposal.json", "output", {"type": "object"}),
        ]
    ]
    variable = "ANTHROPIC_API_KEY" if adapter == "claude" else "CODEX_API_KEY"
    logical = "anthropic-api-key" if adapter == "claude" else "openai-api-key"
    runtime["credentials"] = [
        {
            "name": "native-api",
            "source": {"type": "raw", "secret": logical},
            "delivery": {"type": "environment", "variable": variable},
        }
    ]
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / "lock.json").read_text())
    for adapter in ("claude", "codex"):
        artifact = args.cache / (adapter + ".tgz")
        pin = lock["native"][adapter]
        if not artifact.exists():
            with (
                urllib.request.urlopen(pin["url"], timeout=60) as response,
                artifact.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
        digest = (
            "sha512-" + base64.b64encode(hashlib.sha512(artifact.read_bytes()).digest()).decode()
        )
        if digest != pin["integrity"]:
            raise ValueError("native artifact integrity mismatch: " + adapter)
        with tempfile.TemporaryDirectory(prefix="reference-build-", dir=args.out) as name:
            context = Path(name)
            for filename in ("Dockerfile", "adapter.py"):
                shutil.copyfile(ROOT / filename, context / filename)
            for module in (bootstrap, initializer):
                short = module.__name__.split(".")[-1]
                data = Path(module.__file__).read_bytes()
                if hashlib.sha256(data).hexdigest() != lock[short + "_sha256"]:
                    raise ValueError("installed Karn source differs from reference lock: " + short)
                (context / (short + ".py")).write_bytes(data)
            with tarfile.open(artifact) as archive:
                for member in archive.getmembers():
                    if (
                        not member.isfile()
                        or not member.name.startswith("package/")
                        or ".." in Path(member.name).parts
                    ):
                        raise ValueError("unexpected native artifact member")
                    target = context / "native" / member.name.removeprefix("package/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as stream, target.open("wb") as output:
                        shutil.copyfileobj(stream, output)
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
            result = subprocess.run(
                [
                    "docker",
                    "build",
                    "--build-arg",
                    "ADAPTER=" + adapter,
                    "--iidfile",
                    str(context / "image.id"),
                    str(context),
                ],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            (args.out / (adapter + "-build.log")).write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError("reference image build failed: " + adapter)
            image = (context / "image.id").read_text().strip()
            doc = definition(adapter, image, lock)
            (args.out / (adapter + "-definition.json")).write_bytes(canonical(doc) + b"\n")
            print(adapter + " " + image, flush=True)
    inventory = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ROOT.iterdir()
        if path.is_file()
    }
    (args.out / "build-source.json").write_text(
        json.dumps(
            {"version": 1, "files": inventory, "karn_revision": lock["karn_revision"]},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
