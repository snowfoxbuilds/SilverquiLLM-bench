# Key Decisions

Persistent architectural and convention decisions across runs.


## _REPO_ROOT convention
- **Context**: Item 1 removed configurable `cards_dir`/`engine_dir` params and hardcoded repo-relative paths.
- **Decision**: Both `cli.py` and `workspace.py` define `_REPO_ROOT = Path(__file__).resolve().parent.parent` as a module-level constant. All repo-relative path resolution uses this constant.
- **Reasoning**: Consistent pattern across modules. The spec states cards and engine dirs are repo-relative constants.
- **Impact**: `silverquillm/cli.py`, `silverquillm/workspace.py`.

## Collector number normalization
- **Context**: CLI `--cards` accepts zero-padded collector numbers (e.g., 001, 042) but `card_spec.json` stores unpadded values (e.g., 1, 42).
- **Decision**: Normalize via `str(int(x))` at both CLI parsing and workspace staging for defense-in-depth.
- **Reasoning**: Simple, handles all zero-padding cases, preserves non-numeric collector numbers as-is.
- **Impact**: `silverquillm/cli.py`, `silverquillm/workspace.py`.

## Docker entrypoint output channel pattern
- **Context**: Entrypoints needed structured output separation for multi-channel monitoring.
- **Decision**: JavaScript entrypoints use `log()` helper writing to `/output/system.log`, tee agent output to `/output/agent_stdout.log`, and include SIGTERM handler writing `timed_out` to `progress.jsonl`.
- **Reasoning**: Matches the spec's file-based channel separation. Docker logs still capture agent output via `process.stdout.write()`.
- **Impact**: `docker/homelab-pi-blind/entrypoint.mjs`, `docker/local-pi-blind/entrypoint.mjs`. Future bash entrypoints should follow the reference pattern in the TODO.

## Docker log file naming: .tmp + .log copy
- **Context**: ContainerLifecycle pipe readers write to docker_stdout.tmp/docker_stderr.tmp during container run.
- **Decision**: After pipe threads join, runner.py copies .tmp → .log (using shutil.copy2, not rename). Harvest picks up .log files via glob.
- **Reasoning**: Copy preserves .tmp for debugging while producing .log for harvest. Lifecycle owns the naming, keeping harvest logic simple.
- **Impact**: `silverquillm/runner.py`, `silverquillm/cli.py` (harvest).

## Integration test CLI invocation pattern
- **Context**: Integration tests that invoke the CLI as a subprocess need to use the local checkout, not the installed package.
- **Decision**: Use `[sys.executable, "-m", "silverquillm.cli", ...]` instead of `["silverquillm", ...]` in subprocess calls.
- **Reasoning**: Ensures the test exercises the code from the current worktree, not a potentially stale installed entry point.
- **Impact**: `tests/test_smoke_lifecycle.py`. Future integration tests should follow this pattern.

## Hard-error pattern for workspace reference material
- **Context**: Workspace staging previously used stub fallbacks for missing source files, masking setup errors.
- **Decision**: All workspace reference material (rulebook, rules_overview, test_utils.md) raises `FileNotFoundError` if source is missing. No stub fallbacks.
- **Reasoning**: Silent stubs waste agent budget on useless content and mask misconfigurations.
- **Impact**: `silverquillm/workspace.py` — `_copy_reference_docs()` and rulebook/overview staging.
