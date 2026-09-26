"""The default install runs every command without any TheOzolith package (ADR-014).

The probe runs in a fresh interpreter with an import hook that refuses every
``theozolith*`` module, so a transitive import anywhere in the package, in a
retained script, or behind a lazily imported command body fails the test.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_PROBE = r"""
import importlib
import importlib.abc
import importlib.util
import pkgutil
import sys
from pathlib import Path

repo, scratch = Path(sys.argv[1]), Path(sys.argv[2])


class RefuseOzolith(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.partition(".")[0].startswith("theozolith"):
            raise ModuleNotFoundError(f"blocked import of {name}")
        return None


sys.meta_path.insert(0, RefuseOzolith())
sys.path.insert(0, str(repo))

from click.testing import CliRunner

import silverquillm
from silverquillm.cli import main

for module in pkgutil.walk_packages(silverquillm.__path__, "silverquillm."):
    importlib.import_module(module.name)

for script in sorted((repo / "scripts").glob("*.py")):
    spec = importlib.util.spec_from_file_location(f"retained_{script.stem}", script)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    try:
        spec.loader.exec_module(loaded)
    except ModuleNotFoundError as error:
        # A data tool's own optional dependency (download_replays: curl_cffi)
        # is not the default install's concern; an Ozolith import still fails.
        if "blocked import" in str(error):
            raise


def invoke(*args):
    result = CliRunner().invoke(main, list(args))
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception
    assert result.exit_code == 0, (args, result.output)
    return result.output


def walk(group, prefix):
    for name, command in group.commands.items():
        invoke(*prefix, name, "--help")
        if hasattr(command, "commands"):
            walk(command, [*prefix, name])


walk(main, [])

empty = scratch / "empty"
karn_only = scratch / "karn-only"
mixed = scratch / "mixed"
for directory in (empty, karn_only, mixed):
    directory.mkdir()
for directory in (karn_only, mixed):
    (directory / "trial.toml").write_text('format = "karn-v4"\nruns = []\n')
(mixed / "old.toml").write_text('[[runs]]\ncandidate = "candidates/x"\nbenchmark = "smoke"\n')

assert invoke("queue", "ls", "--batches-dir", str(empty)).strip() == "no batches"
assert "trial [karn-v4]: missing_state (0/0)" in invoke("queue", "ls", "--batches-dir", str(karn_only))
listed = invoke("queue", "ls", "--batches-dir", str(mixed))
assert "trial [karn-v4]" in listed and "old [legacy]: unsupported legacy batch" in listed, listed
assert '"unsupported_legacy_batch"' in invoke("queue", "ls", "--json", "--batches-dir", str(mixed))
assert "unsupported legacy batch" in invoke("top", "--batches-dir", str(mixed))

options = []
for flag in ("--bench-root", "--results-dir", "--results-repo", "--state-root"):
    target = scratch / flag.strip("-")
    target.mkdir()
    options += [flag, str(target)]
from silverquillm.karn import grader as grader_module

# The scheduler checks for the grader image before starting; Docker stays out of unit tests.
grader_module.DockerRunner.image_id = lambda self, reference: "sha256:" + "0" * 64
assert "0 run(s) executed" in invoke("scheduler", "--once", "--batches-dir", str(empty), *options)
missing = CliRunner().invoke(main, ["recover", "absent", *options])
assert missing.exit_code == 1 and "run_not_found:absent" in missing.output, missing.output

assert not [name for name in sys.modules if name.startswith("theozolith")]
print("ok")
"""


def test_every_module_script_and_command_runs_without_ozolith(tmp_path: Path) -> None:
    checked = subprocess.run(
        [sys.executable, "-c", _PROBE, str(REPO), str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert checked.returncode == 0, checked.stdout[-4000:] + checked.stderr[-4000:]
    assert checked.stdout.strip().endswith("ok")


def test_no_dependency_or_extra_names_ozolith() -> None:
    project = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
    requirements = list(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        requirements += extra
    assert "legacy" not in project.get("optional-dependencies", {})
    assert not [r for r in requirements if "ozolith" in r.lower()], requirements
