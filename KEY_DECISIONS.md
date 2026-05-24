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

