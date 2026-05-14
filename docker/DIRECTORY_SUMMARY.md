# Directory Summary — `docker/`

## Purpose

Docker agent container definitions for the SilverquiLLM benchmark. Each subdirectory defines a complete agent image (Dockerfile + entrypoint + model config) that receives a mounted workspace, runs an LLM agent, and produces card implementations.

## Subdirectories

| Directory | Contents |
|-----------|----------|
| `homelab-pi-blind/` | **Homelab Pi blind agent** — `Dockerfile`, `entrypoint.mjs` (Node.js), `models.json`. Multi-channel output capture with timestamped `agentStdout()`/`agentStderr()` helpers, stderr interceptor for agent runtime capture, try/catch/finally for guaranteed `exit_code` reporting. |
| `local-pi-blind/` | **Local Pi blind agent** — Same structure and multi-channel output changes as homelab variant. `Dockerfile`, `entrypoint.mjs`, `models.json`. |

## Architecture

- **Black-box containers**: Each image is the full agent configuration — it bakes in the agent CLI, mode (blind/tested), strategy, model, and prompt. The runner passes only workspace/output volumes, API keys, and a timeout.
- **Entrypoint pattern**: `entrypoint.mjs` (Node.js) manages agent lifecycle with multi-channel output capture (stdout, stderr, agent-specific channels). Timestamps all log lines. Guarantees `exit_code` is written even on errors.
- **File-based contract**: Container reads from `/workspace/` (staged by runner) and writes results to `/output/`.

## Dependencies

- **Upstream**: `silverquillm/cli.py` builds and launches these containers via `docker run`.
- **Downstream**: Results harvested by `silverquillm/cli.py` → `_harvest_results()`.
