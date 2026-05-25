# Directory Summary — `docker/`

## Purpose

Docker image definitions for agent runtime environments. Each subdirectory contains a Dockerfile, entrypoint script, and model configuration for a specific agent/hardware combination.

## Subdirectories

| Directory | Agent | Description |
|-----------|-------|-------------|
| `homelab-pi-blind/` | Pi coding agent (homelab GPU) | Dockerfile + Node.js entrypoint for Pi agent on homelab hardware. |
| `local-pi-blind/` | Pi coding agent (local) | Dockerfile + Node.js entrypoint for Pi agent on local hardware. |

## Entrypoint Pattern

Both entrypoints (`entrypoint.mjs`) follow a consistent pattern:
- **System log**: `log()` helper writes timestamped messages to `/output/system.log`.
- **Agent output capture**: Agent stdout is tee'd to `/output/agent_stdout.log`.
- **SIGTERM handler**: Catches SIGTERM, terminates the agent process, then exits cleanly.
- **No engine copy**: Engine work directory is not copied into the container (engine is staged in workspace by `silverquillm/workspace.py`).
- **No progress.jsonl**: Progress channel removed; startup/completion messages go to system.log instead.

## Files per Subdirectory

| File | Responsibility |
|------|---------------|
| `Dockerfile` | Image build definition. |
| `entrypoint.mjs` | Node.js entry script — agent session setup, output capture, SIGTERM handling. |
| `models.json` | Model configuration for the agent. |

## Developer Guide

- **Adding a new agent image**: Create a new subdirectory with `Dockerfile`, `entrypoint.mjs`, and `models.json`. Follow the existing entrypoint pattern (system.log, agent_stdout.log, SIGTERM handler).
- **Testing**: Entrypoint behavior is validated by `tests/test_docker_entrypoints.py`.
