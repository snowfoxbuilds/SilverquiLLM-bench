Status: ACCEPTED
Date: 2026-11-07

# ADR-022: pi Constructs Run Against a Bench-Started Local Model Server

## Context

Local models served by llama.cpp are benchmarked through Karn's `pi@1` constructs, which run `pi --print --no-session` and leave no native journal or transcript.
The bench read requests only from Claude and Codex journals, so a pi run recorded none, and its model and subagent attributes were unknown.
Restricted egress reaches only public HTTPS hosts, and `open` egress gives the workload the whole internet.
The server's settings (model file, quantization, context, KV-cache type) decide the result as much as the model does, so they must be part of the candidate.

## Decision

A recipe declares its server in `runtime.environment` as `SILVERQUILLM_MODEL_SERVER`: the llama.cpp build, one model file with its sha256, and server flags from a bench allowlist.
Being in the definition, the server is part of the `candidate_hash`, and each configuration is its own campaign.
The recipe also sets `CONSTRUCT_PI_BASE_URL = "http://model-server:8080/v1"` and `restricted` egress.

The host config maps each llama.cpp build to a binary and names a models directory.
Before any evidence exists, the bench refuses a missing build, a binary whose `--version` reports another build, or a missing model file.
During the run, it holds a host-wide lock, verifies the file's digest, and starts `llama-server` on loopback with the recipe's flags and the construct's model as its alias.
A host-side relay forwards each request to the server and records its usage, the server's timings and a compact transcript.
The workload reaches the relay only through the run's proxy sidecar, whose one plain-HTTP listener the workload resolves as `model-server` and which serves only the run's own internal network.
The relay's measurements carry one thread, and subagent use as unknown: one server answers every agent process, so the relay cannot count them.

## Consequences

- **Positive**: a pi run's records count: every request, its model, token usage and generation speed are observed by the bench itself, not by the workload.
- **Positive**: the workload has no internet; its only route out is the model server.
- **Positive**: no GPU container runtime is needed; the server runs as an ordinary host process.
- **Negative**: the served model's name is the alias the bench gives it, so `model_match` holds by construction; the model's identity is the verified file digest in the record.
- **Negative**: a campaign of these runs cannot require `no_subagents`; pi has no subagent tool, but the workload could start a second agent process unseen.
- **Negative**: a request can override the server's sampling settings; the relay records such overrides but does not refuse them.
- **Negative**: the host must keep each pinned build and model file for as long as its candidates run; a rebuilt binary with the same build number is not detected.
- **Neutral**: no price applies, so the Estimated Cost stays incomplete with `model_price_unavailable`, and usage is partial because llama.cpp does not split reasoning tokens out of completion tokens.

## Alternatives Considered

- **`open` egress to a server the operator runs**: the workload would have the internet, and nothing would tie the server's settings to the record.
- **A llama-server container with GPU access**: needs the NVIDIA container runtime on every host, and the Karn definition has no device field to carry it.
- **Harvesting pi's own session files**: the pi adapter runs with `--no-session`, and a workload-written file would be the only record of its requests.
