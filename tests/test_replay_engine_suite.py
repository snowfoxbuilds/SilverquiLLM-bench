"""Run the host-side replay-tool suite against hob-medium's baseline engine.

It runs in a subprocess because it imports the workspace's top-level
``engine`` package, which would collide with other benchmarks' engines in this
process.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUITE = REPO_ROOT / "benchmarks" / "hob-medium" / "replay_tests"


def test_replay_suite_passes_on_the_baseline_engine():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(SUITE), "-q", "-p", "no:cacheprovider"],
        cwd=SUITE,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
