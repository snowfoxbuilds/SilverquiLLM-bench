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
