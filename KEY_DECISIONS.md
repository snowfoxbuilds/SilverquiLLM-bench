# Key Decisions

Persistent architectural and convention decisions across runs.


## _REPO_ROOT convention
- **Context**: Item 1 removed configurable `cards_dir`/`engine_dir` params and hardcoded repo-relative paths.
- **Decision**: Both `cli.py` and `workspace.py` define `_REPO_ROOT = Path(__file__).resolve().parent.parent` as a module-level constant. All repo-relative path resolution uses this constant.
- **Reasoning**: Consistent pattern across modules. The spec states cards and engine dirs are repo-relative constants.
- **Impact**: `silverquillm/cli.py`, `silverquillm/workspace.py`.
