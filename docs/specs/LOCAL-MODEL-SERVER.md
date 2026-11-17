Status: DRAFT
Last updated: 2026-11-16

# Local Model Server

A construct may be served by a llama.cpp `llama-server` the bench starts on the host for each run, pinned to one of the host's GPU Slots and observed by a host-side relay.

## Context

Local models have no provider journal, and the server's settings decide the result as much as the model does.
The bench therefore starts the server itself, from settings in the candidate's definition, and records every request it serves.
This page extends the [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md), which owns the run lifecycle around it.

## Design

A construct may be served by a llama.cpp `llama-server` the bench starts for each run.
Three owners split the server's settings (grilling 2026-11-16), so a surprise on a new host is fixed in the recipe or the host config, not in the bench:

| Owner | Owns |
| --- | --- |
| The recipe, part of the candidate | everything that changes the result: flags, files, the server's environment, timeouts |
| The host config | what only this host needs: binary paths, `models_dir`, `gpu_slots`, a host environment |
| The bench | what keeps the record true: the model's identity, the address and alias, the network isolation, the relay |

### Recipe declaration

The recipe declares the server as `SILVERQUILLM_MODEL_SERVER` in `runtime.environment`, a JSON object with these keys:

| Key | Holds |
| --- | --- |
| `engine` | `"llama.cpp"` |
| `build` | the llama.cpp build, as `b12182` |
| `model` or `files` | `model`: `{"file": "<name>.gguf", "sha256": "<64 hex>"}`; or `files`, a list of `{"file", "sha256", "flag"?}`, each a file in the host's models directory, passed after its `flag`, or not passed when it has none, as the later shards of a split model |
| `arguments` | server flags, any but the bench's own |
| `environment` (optional) | variables for the server process, as `GGML_CUDA_*` |
| `ready_seconds` (optional) | how long the server may take to become ready, default 900 |
| `request_timeout_seconds` (optional) | how long one relayed request may take, default 1800 |

Under `files`, exactly one entry has the flag `--model`, and that entry is the model; `model` is that one entry alone (grilling 2026-11-16).
A recipe without the optional keys keeps its definition, and so its candidate hash, unchanged.

The recipe also sets a `CONSTRUCT_MODEL` and `restricted` egress, an empty `https_hosts` meaning no internet, and points its agent at `http://model-server:8080/v1` through whatever variable the agent reads, as `CONSTRUCT_PI_BASE_URL` for pi; the bench does not check which (grilling 2026-11-16).

The bench refuses only the flags it owns or that would defeat the record (grilling 2026-11-16):

| Refused | Why |
| --- | --- |
| `--host`, `--port`, `--path`, `--api-key`, `--api-key-file`, `--webui`, `--no-webui`, `--ssl-*` | the bench owns the address and API surface |
| `-m`, `--model`, `-hf*`, `-mu`, `--model-url`, `--alias`, `-a`, `--lora*`, `--control-vector*` | the model's identity is the verified files and the bench's alias |
| `--rpc` | the server reaches no other host |
| `--log-file`, `--slot-save-path` | the server writes only where the bench puts it |
| any other flag naming an input file | an input file is declared in `files`, so its digest is verified and recorded |

`environment` refuses `LLAMA_ARG_*`, which llama.cpp reads as flags, and `CUDA_VISIBLE_DEVICES` and `CUDA_DEVICE_ORDER`, which the GPU Slot sets.

### Host configuration

The host config's `[model_server]` table names `models_dir`, maps each build to its binary under `[model_server.llama_cpp]`, and may set `environment`, variables only this host's builds need, as an `LD_LIBRARY_PATH` for a dynamically linked llama.cpp (grilling 2026-11-16); it refuses the same variables a recipe's `environment` does.
Before any evidence exists, a run is refused if the build is not mapped, if the binary's `--version` reports another build, or if a declared file is missing.

### GPU Slots

A host serves as many model-server runs at once as it has GPU Slots (grilling 2026-11-16).
`[model_server] gpu_slots` lists them, each a `CUDA_VISIBLE_DEVICES` value such as `"0"` or `"0,1"`, and a host config whose GPU Slots share a GPU is refused.
Without `gpu_slots` the host has one GPU Slot, locked by `<state_root>/model-server.lock`, and the server sees every GPU the runner sees.
With them, each GPU Slot's lock is named by its value (`model-server-gpu-0.lock`), so reordering the list never moves a held lock onto another GPU; the operator changes `gpu_slots` only while the scheduler is drained.

A run claims the first free GPU Slot before it is recorded as started, the way a run claims a Login Profile.
A GPU Slot is free when its lock is free, no compute process runs on its GPUs, and none of its GPUs reports more than 1 GiB of memory used: another user's job, or the server of a runner that has just died, keeps it busy.
The memory bound catches a job whose process `nvidia-smi` does not list to the operator's user (grilling 2026-11-16).
A direct `silverquillm run` finding no free GPU Slot is refused with `model_server_busy`, before any evidence exists; the scheduler defers the entry, in queue order, until one frees.
The GPU Slot is released when the server stops, so another run may claim it while this one grades.

### Serving a run

Once its GPU Slot is claimed, the run:

1. verifies every declared file's sha256;
2. starts `llama-server` on loopback with the recipe's flags and files and `--alias <CONSTRUCT_MODEL>`, logging to `model-server.log` in the run directory;
3. relays every request to it from a host-side relay on a secret path.

The server never inherits the runner's environment, where a stray `LD_LIBRARY_PATH` or `LLAMA_ARG_*` would change it unseen (grilling 2026-11-16).
It starts with `PATH` and `HOME`, then the host config's `environment`, then the recipe's, then `CUDA_DEVICE_ORDER=PCI_BUS_ID`, so CUDA numbers the GPUs as `nvidia-smi` does, and, when `gpu_slots` is set, the GPU Slot's `CUDA_VISIBLE_DEVICES`.

The proxy sidecar listens on port 8080 too, serves only clients on the run's own internal network, and forwards only `/v1/` requests of at most 16 MiB, one per connection, to that relay; the workload resolves it as `model-server` through `--add-host`.
The relay passes on only `POST /v1/chat/completions` and `GET /v1/models`, and refuses a request for more than one choice (`n`).
The server stops with the run, before grading, and with the runner if the runner dies.

### Recorded facts

Before the run launches its workload, `run-input.json` holds the server facts the run verified, so a recovered record carries the same `run_metadata.model_server` and `native_telemetry`.
`run_metadata.model_server.host` records the host's side of the server, which is not part of the candidate (grilling 2026-11-16):

| Field | Holds |
| --- | --- |
| `gpu_slot` | the claimed GPU Slot's value, or null without `gpu_slots` |
| `gpus` | per visible GPU, from `nvidia-smi` at claim: name, UUID, total and used memory, power limit, driver version |
| `binary_sha256` | the llama-server binary's digest, recorded and never checked |
| `environment` | the host config's `environment` for the server |

When `nvidia-smi` is missing or fails, `gpus` is null with a reason and the run goes ahead.
Recovery copies all these facts as recorded, never claims a GPU Slot and never reverifies the host's current files; a run interrupted before verification is recovered with `model_sha256_verified` null.

### Relay observations

The relay is the run's only observation source, so it cannot be combined with `--native-telemetry` other than `auto`.
Each relayed request becomes one request row on thread `main`, with the served model, its usage, `finish_reason` and the server's own `timings`.
Every request reaches one server, so the relay cannot tell a second agent process from the main one: subagent use is unknown (`subagents` null, `subagents_reason` `threads_not_observable`), never `none`.
The relay writes a `request_started` event to `observations.events.jsonl` before it forwards a request, and a `response` event with the same id when the request settles.
When the run ends, the relay stops admitting requests, cancels those still in flight, and waits at most 10 seconds for their `response` events; nothing is recorded after the measurements are computed, so the events file always summarizes to the record's measurements.
A start with no `response`, from a runner that died or a request that did not settle in time, counts as an unfinished request.
An event counts only once it is written whole: a failed write is cut back before the next one, the relay stops admitting requests when it cannot be, and a request whose terminal event cannot be written stays unfinished, so the live and recovered summaries agree.
Recovery reads only the newline-terminated lines of the relay's events file; an unterminated last line, even one that parses, is ignored with `interrupted_observation_line`.
A response with status 200 is complete only when it carries a final choice (`finish_reason`) and, for a stream, ends with `data: [DONE]`; one the server ends early is failed with `upstream_response_incomplete`, or `upstream_response_truncated` when a fixed-length body is cut short.
A complete response that reports no usage still counts, with usage partial (`response_usage_missing`).
A request that failed, was cancelled or was unfinished, or a response that reported usage more than once, leaves usage partial (`relayed_request_incomplete`, `multiple_usage_reports`).
Usage follows OpenAI's convention, input including cached tokens; cache writes are zero, and reasoning tokens are missing, because llama.cpp counts them inside completion tokens.
No price applies, whatever name the recipe serves the model under: requests are priced from an empty table (`price_table.models` is empty), so the Estimated Cost is unavailable with `model_price_unavailable`.
`measurements.server_timings` sums the server's prompt and generation tokens and times into tokens per second, `coverage.failed_requests` counts requests the relay could not complete, and `coverage.unfinished_requests` those of them that never settled.
A request may set sampling parameters of its own, which llama.cpp honours over the server's flags; each event keeps them as `request_parameters`, and `coverage.requests_with_parameter_overrides` counts such requests.
`run_metadata.model_server` records the spec, the binary and its version, the verified digest, and how long verification and start-up took.
The run directory also keeps `model-transcript.jsonl`: per request, the messages added since the last reply and the assembled response, with its reasoning and tool calls.
A transcript row that cannot be written leaves its request's record unchanged; `coverage.transcript_rows_missing` counts such rows.
What the relay keeps of workload-controlled content is bounded: 1 MiB of messages and of response per request, and a few KiB for each other field, cut with `truncated_from_chars`.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-022](../adr/ADR-022-pi-constructs-run-against-a-bench-started-local-model-server.md) | pi constructs run against a bench-started llama.cpp server, observed by a host-side relay |
