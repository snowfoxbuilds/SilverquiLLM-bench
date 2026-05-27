# Key Decisions

Persistent architectural and convention decisions across runs. Periodically drained into specs/ADRs

## Docker stdout/stderr direct-write carve-out

`_drain_pipe` in `silverquillm/runner.py` streams Docker stdout/stderr directly to
`run_dir/docker_stdout.log` and `run_dir/docker_stderr.log` in real time (append mode,
line-buffered, UTF-8 with error replacement). This intentionally breaks the general
`.tmp` → `.log` → harvest-copy convention used by other output files. The `.tmp` files
in `output/` are still written for backward compatibility and local diagnostics, but
the authoritative real-time logs live in `run_dir`. `_harvest_results` in `cli.py`
skips these two files since they are already present in `run_dir`.


## Oracle workspace stub detection uses AST parsing

- **Context**: The harness needs to detect which `card_impl.py` files are real oracle implementations vs empty stubs.
- **Decision**: `_is_stub_impl()` uses Python's AST module to check if any class defines a non-dunder method (e.g., `on_resolve`, `can_cast`, `get_targets`). Classes that only have `__init__` with attribute assignments are still stubs.
- **Reasoning**: Simple text-matching or regex could be fooled. AST parsing is robust and aligns with the semantics: a card impl is "real" when it defines game logic methods.
- **Impact**: `tests/test_audited_against_reference.py`

## resolve_top() vs _resolve_top_of_stack() semantics

- **Context**: The oracle workspace `test_utils.py` needed both a "resolve one stack object" helper and the existing "drain full stack" behavior.
- **Decision**: `resolve_top()` resolves exactly one stack object (pop + resolve + SBA). `_resolve_top_of_stack()` drains the entire stack with a while loop. `cast_spell()` uses `_resolve_top_of_stack()` to drain all triggers.
- **Reasoning**: Tests need fine-grained control (resolve one thing at a time) while `cast_spell()` needs the convenience of auto-draining.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/test_utils.py`

