"""Benchmark data and implementation-only task staging for Karn runs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .definition import KarnError, canonical, digest
from .snapshots import copy_workspace


@dataclass(frozen=True)
class Benchmark:
    id: str
    root: Path
    config: dict

    @property
    def target_set(self) -> str:
        return self.config["draft_set"]["primary_set_code"].lower()

    @property
    def cards(self) -> list[str]:
        return [str(number) for number in self.config["cards"]]

    @property
    def identity(self) -> dict:
        return {
            "id": self.id,
            "configuration_digest": digest(canonical(self.config)),
            "target_set": self.target_set,
            "cards": self.cards,
        }


def load_benchmark(bench_root: Path, benchmark_id: str) -> Benchmark:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", benchmark_id):
        raise KarnError("invalid_benchmark_id")
    root = Path(bench_root).resolve() / "benchmarks" / benchmark_id
    try:
        config = json.loads((root / "config.json").read_text())
        if config.get("id", benchmark_id) != benchmark_id or not config["cards"]:
            raise ValueError
        target = config["draft_set"]["primary_set_code"]
        if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9]+", target):
            raise ValueError
        if not (root / "workspace").is_dir():
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise KarnError("benchmark_unavailable:" + benchmark_id) from None
    return Benchmark(benchmark_id, root, config)


def stage_benchmark(benchmark: Benchmark, destination: Path) -> tuple[str, dict]:
    copied = copy_workspace(benchmark.root / "workspace", destination)
    if copied["errors"]:
        raise KarnError("benchmark_workspace_incomplete")
    selected = {str(int(number)) if number.isdigit() else number for number in benchmark.cards}
    targets = []
    for directory in sorted((destination / "cards" / benchmark.target_set).iterdir()):
        spec = directory / "card_spec.json"
        if not directory.is_dir() or not spec.is_file():
            continue
        data = json.loads(spec.read_text())
        number = str(data["collector_number"])
        number = str(int(number)) if number.isdigit() else number
        if number in selected:
            targets.append(str(directory.relative_to(destination)))
    if len(targets) != len(selected):
        raise KarnError("benchmark_selected_cards_missing")
    instruction = benchmark.root / "instructions.md"
    guidance = (
        instruction.read_text()
        if instruction.is_file()
        else "Read the Workspace guidance and each selected card's instructions.md when present."
    )
    prompt = (
        f"Implement the selected cards for {benchmark.id} in your Workspace.\n\n"
        + "\n".join("- " + target for target in targets)
        + "\n\nUse card_spec.json as the card definition and existing FDN cards as examples. "
        "You may change the engine to support the required mechanics. "
        "Keep existing card and engine behavior working. The implementation files are the requested result.\n\n"
        + guidance
        + "\n"
    )
    git_environment = {
        "PATH": os.defpath,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    git = [
        "git",
        "-C",
        str(destination),
        "-c",
        "user.name=SilverquiLLM Bench",
        "-c",
        "user.email=benchmark@example.invalid",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "commit.gpgsign=false",
    ]
    for arguments in (
        ["-c", "init.defaultBranch=benchmark", "init", "--template=", "--quiet"],
        ["add", "--all"],
        ["commit", "--quiet", "-m", "Stage benchmark workspace"],
    ):
        subprocess.run(
            [*git, *arguments], env=git_environment, check=True, capture_output=True, timeout=30
        )
    baseline = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        env=git_environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    return prompt, {
        **benchmark.identity,
        "workspace_digest": copied["digest"],
        "baseline_commit": baseline,
        "prompt_digest": digest(prompt.encode()),
    }
