Status: DRAFT
Last updated: 2026-11-19

# Local Model Server

A construct may be served by a llama.cpp `llama-server` the bench starts on the host for each run, pinned to one of the host's GPU Slots when it lists them, and observed by a host-side relay.

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
| `ready_timeout_seconds` (optional) | how long the server may take to become ready, default 900; named apart from the measured `ready_seconds` the record keeps (#271) |
| `request_timeout_seconds` (optional) | how long one model request may stay silent, default 1800; it governs every hop, the sidecar's route to the relay and the relay's request to the server (#275) |

Under `files`, exactly one entry has the flag `--model`, and that entry is the model; `model` is that one entry alone (grilling 2026-11-16).
A file is named by its bare name in the models directory, never a path, and a split model lists every part, since llama.cpp loads the later parts by name (#271).
A file's flag may be any flag but those refused below; `model` names a single `.gguf` file that is not a split part.
A recipe without the optional keys keeps its definition, and so its candidate hash, unchanged.

The recipe also sets a `CONSTRUCT_MODEL` and `restricted` egress, an empty `https_hosts` meaning no internet, and points its agent at `http://model-server:8080/v1` through whatever variable the agent reads, as `CONSTRUCT_PI_BASE_URL` for pi, or at `http://model-server:8080` as `ANTHROPIC_BASE_URL` for Claude Code, which adds `/v1/messages` itself; the bench does not check which (grilling 2026-11-16, #287).

The bench refuses only the flags it owns or that would defeat the record (grilling 2026-11-16):

| Refused | Why |
| --- | --- |
| `--host`, `--port`, `--path`, `--api-prefix`, `--api-key`, `--api-key-file`, `--ui`/`--webui` and their `--no-` and `-config` forms, `--ssl-key-file`, `--ssl-cert-file`, `--reuse-port` | the bench owns the address and API surface |
| `-mu`, `--model-url`, `-dr`, `--docker-repo`, `-hf`, `-hfr`, `--hf-repo`, `-hff`, `--hf-file`, `-hft`, `--hf-token`, `-hfd`, `-hfrd`, `--hf-repo-draft`, `--spec-draft-hf`, `-mmu`, `--mmproj-url`, `-a`, `--alias`, `--models-dir`, `--models-preset` | the model's identity is the verified files and the bench's alias |
| the presets `--embd-gemma-default`, `--fim-qwen-{1.5b,3b,7b,30b}-default`, `--fim-qwen-{7b,14b}-spec`, `--gpt-oss-{20b,120b}-default`, `--vision-gemma-{4b,12b}-default` | each downloads a model and moves the port (grilling 2026-11-16) |
| `--rpc`, `--tools`, `--tools-runtime`, `--mcp-servers-config`, `--mcp-servers-json`, the `--ui-mcp-proxy` forms, `-ag`/`--agent` and its `--no-` forms, `--connect`, `--connect-code` | the server reaches no other host and runs nothing on this one for a request |
| `--log-file`, `--slot-save-path`, `--log-prompts-dir`, `--media-path`, `--video-ffmpeg-dir`, `-lcd`, `--lookup-cache-dynamic` | the server writes, and reads for a request, only where the bench puts it |
| `--lora-scaled`, `--control-vector-scaled`, as arguments and as a `files` flag | they take `FNAME:SCALE`, and a `files` entry declares no scale: `files` supports the unscaled `--lora` and `--control-vector` only (#275) |

The bench also refuses, among the arguments only, the flags of llama.cpp b12182 that name an input file: `-m`, `--model`, `-md`, `--model-draft`, `--spec-draft-model`, `-mm`, `--mmproj`, `--chat-template-file`, `--grammar-file`, `-jf`, `--json-schema-file`, `-lcs`, `--lookup-cache-static`, `--lora`, `--control-vector`, `-f`, `--file`, `-bf` and `--binary-file`.
Such a file is declared in `files` instead, so its digest is verified and recorded (#271).
A flag is refused alone or as `--flag=value`, and every argument is checked, a value too, so a refused flag cannot hide as one; every other flag passes and is recorded with the arguments; a later build's new file flag passes unverified until it is added to that list.
llama.cpp rewrites `_` to `-` in every argument starting with `--` before it looks the flag up, so the bench compares the same rewritten name: `--hf_repo` is refused as `--hf-repo` (grilling 2026-11-16).

`environment` refuses every variable llama.cpp b12182 reads as an option, a port or route, a config, cache or download location, or a library path, and every one the bench sets itself (grilling 2026-11-16):

| Refused | Why |
| --- | --- |
| `LLAMA_*` (as `LLAMA_ARG_*`, `LLAMA_API_KEY`, `LLAMA_CACHE`, `LLAMA_SERVER_*`), `LLAMACPP_*`, `MTMD_BACKEND_DEVICE` | llama.cpp reads them as flags or server settings |
| `MTMD_DEBUG_EMBEDDINGS`, `GGML_ET_PROFILE`, `CUDA_CACHE_PATH`, `CUDA_MPS_LOG_DIRECTORY`, and any name ending `_LOG_FILE` or containing `LOGDEST` or `COREDUMP`, as `CUDA_LOG_FILE`, `CUBLASLT_LOG_FILE`, `CUBLAS_LOGDEST_DBG`, `CUDA_COREDUMP_FILE` | they write to a host path (grilling 2026-11-16) |
| `AIP_*` | they move the server's port and routes |
| `HF_*`, `HUGGING_FACE_*`, `HUGGINGFACE_*`, `MODEL_ENDPOINT`, and `http_proxy`, `https_proxy`, `all_proxy`, `no_proxy` in any case | they name download sources, caches and routes out |
| `LD_*`, `GGML_BACKEND_PATH`, `GGML_ET_KERNELS_PATH`, `GGML_OPENCL_KERNEL_CACHE_DIR`, `ET_TOOLCHAIN`, `TOOLCHAIN_ROOT`, `GCONV_PATH`, libcuda's `CUDA_INJECTION64_PATH`, `CUDA_INJECTION32_PATH`, `CUDA_AMODEL_DLL`, `CUDA_FORCE_PRELOAD_LIBRARIES`, `CUDA_DEVCODE_PATH`, `CUDA_MPS_PIPE_DIRECTORY`, and `OPENSSL_*`, `SSL_CERT_*` | they choose the code the server loads (grilling 2026-11-16) |
| `PATH`, `HOME`, `XDG_*`, `CUDA_VISIBLE_DEVICES`, `CUDA_DEVICE_ORDER`, names starting `__` | the bench sets them, or passes the runner's GPU selection |
| `GGML_VK_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES`, `ROCR_VISIBLE_DEVICES` | they would select GPUs behind a GPU Slot's back on a build that reads them (#269) |

These lists guard against an operator's mistake, not a hostile recipe author: recipes are written by the operator and recorded in full in the definition, so a variable or flag missing from them is still visible in the record (grilling 2026-11-16).
A host `LD_LIBRARY_PATH` is likewise the operator's, and recorded, but the libraries it points at are not (grilling 2026-11-16).

### Host configuration

The host config's `[model_server]` table names `models_dir`, maps each build to its binary under `[model_server.llama_cpp]`, and may set `environment`, variables only this host's builds need, as an `LD_LIBRARY_PATH` for a dynamically linked llama.cpp (grilling 2026-11-16); it refuses the same variables a recipe's `environment` does, except `LD_LIBRARY_PATH` (grilling 2026-11-16).
A run is refused before any evidence exists while a config file llama.cpp reads whatever its environment says is present, `/etc/llama.cpp/config.ini` in b12182, with `model_server_config_file_present:<path>` (grilling 2026-11-16).
Before any evidence exists, a run is refused if the build is not mapped, if the binary's `--version` reports another build, or if a declared file is missing.

### GPU Slots

A host that lists GPU Slots serves as many model-server runs at once as it has GPU Slots (grilling 2026-11-16).
`[model_server] gpu_slots` lists them, each a `CUDA_VISIBLE_DEVICES` value such as `"0"` or `"0,1"`, and a host config whose GPU Slots share a GPU is refused.
A host need not list `gpu_slots`, and then serves model-server runs exactly as before GPU Slots existed (grilling 2026-11-16): one run at a time, under `<state_root>/model-server.lock`, on the GPUs the runner's own `CUDA_VISIBLE_DEVICES` and `CUDA_DEVICE_ORDER` select, with no busy check, since a host's own display or other work may hold GPU memory there.
With them, each GPU Slot's lock is named by its value (`model-server-gpu-0.lock`), so reordering the list never moves a held lock onto another GPU; the operator changes `gpu_slots` only while the scheduler is drained.
GPU Slots pin CUDA builds through `CUDA_VISIBLE_DEVICES`; other backends' device selectors are not managed, and llama.cpp's `-dev` and `--main-gpu` still choose among the GPUs a slot makes visible (#269).

A run claims the first free GPU Slot, or the host-wide lock without `gpu_slots`, before it is recorded as started, the way a run claims a Login Profile, and before the host's preflight and the server's `--version` probe, so a run that finds nothing free costs nothing more (#269).
With `gpu_slots`, a GPU Slot is free when its lock is free, no compute process runs on its GPUs, and none of its GPUs reports more than 1 GiB of memory used: another user's job, or the server of a runner that has just died, keeps it busy.
The memory bound catches a job whose process `nvidia-smi` does not list to the operator's user (grilling 2026-11-16).
A direct `silverquillm run` finding nothing free is refused with `model_server_busy`, before any evidence exists; the scheduler defers the entry, in queue order, until one frees.
Two things make a GPU Slot unusable, and an unusable slot is skipped and reported, never a failed run or a stopped scheduler (#269):

- a lock file the operator's user cannot open, as one left owned by root, reported as `model_server_lock_unusable`;
- a slot naming a GPU that a readable `nvidia-smi` does not list, reported as `gpu_slot_unknown_gpu:<value>`, rather than serving on no GPU.

When no GPU Slot is usable at all because of unknown GPUs, the refusal is `gpu_slot_unknown_gpu:<values>`; like `model_server_busy`, it defers the entry, and a direct run reports every unusable slot with it.
The scheduler judges whether something is free from the kernel's lock table and one `nvidia-smi` reading per pass, never by taking a lock a run is about to claim; the claim itself decides.
`nvidia-smi` is given 10 seconds and abandoned, never waited on, past them.
No probe touches the driver before it is recorded (#269).
A probe starts as a stand-in that waits for the word to go; the starter records its PID and start time in `<state_root>/nvidia-smi-probe.json`, and only then lets it become `nvidia-smi`.
If recording fails, the starter is interrupted, or it dies first, the stand-in ends without running `nvidia-smi`, it is reaped, and the reading is `nvidia_smi_unavailable`.
Once let go, the probe stays recorded until it is confirmed gone, even when killing it does not complete.
While a recorded probe lives, no worker, scheduler or direct run on the host starts another, and readings are `nvidia_smi_unavailable`.
The record outlives the process that started it, so a driver stuck in the kernel costs the host one process, not one per reading or per worker.
A record is live only when it holds an integer PID and an integer start time that the running process still has, so a reused PID never counts; any other record, a malformed or null one included, is stale and is replaced by the next probe.
Its output must be UTF-8 with every number in plain ASCII digits, a bracketed `[N/A]` read as null, else the reading is `nvidia_smi_unreadable`.
The claim is released once the server is confirmed stopped, so another run may claim it while this one grades; the claim knows its server, so no way of releasing it frees the GPUs early, and a server that outlives its stop keeps the claim held until the runner exits (#269).

### Serving a run

Once its claim is held, the run:

1. verifies every declared file's sha256;
2. starts `llama-server` on loopback with the recipe's flags and files and `--alias <CONSTRUCT_MODEL>`, logging to `model-server.log` in the run directory;
3. relays every request to it from a host-side relay on a secret path.

The server never inherits the runner's environment, where a stray `LD_LIBRARY_PATH` or `LLAMA_ARG_*` would change it unseen (grilling 2026-11-16).
It starts with the runner's `PATH`, then the host config's `environment`, then the recipe's, then `HOME` and `XDG_CONFIG_HOME` pointed at an empty directory the bench owns (`model-server-home` in the run directory), so llama.cpp reads no user-level `config.ini`, then the GPU selection: with `gpu_slots`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, so CUDA numbers the GPUs as `nvidia-smi` does, and the GPU Slot's `CUDA_VISIBLE_DEVICES`; without them, the runner's own `CUDA_VISIBLE_DEVICES` and `CUDA_DEVICE_ORDER`, each passed exactly as set, empty or absent, and nothing else of the runner's (grilling 2026-11-16).
The `--version` probe that checks the build runs in the same environment, with a temporary empty home and the claimed GPU selection, so the build verified is the build served, a host `LD_LIBRARY_PATH` applies to both, and on a host with GPU Slots the probe touches no other slot's GPUs (grilling 2026-11-16).
`setpriv`, which stops the server when the runner dies, is found on the runner's `PATH` before the server's environment is built, and a host without it refuses the run before any evidence exists.
Each file is passed by its declared name in the models directory, after its target is found inside that directory, so llama.cpp derives a split model's other parts from declared names only (grilling 2026-11-16).

The proxy sidecar listens on port 8080 too, serves only clients on the run's own internal network, and forwards only `/v1/` requests of at most 16 MiB, one per connection, to that relay, with at most a plain query (letters, digits, `._=&-`), as Claude Code's `?beta=true`; the workload resolves it as `model-server` through `--add-host`.
The relay passes on only `POST /v1/chat/completions`, the chat-completions API pi uses, `POST /v1/messages`, the Anthropic Messages API Claude Code uses, `POST /v1/messages/count_tokens` and `GET /v1/models` (#287).
It drops a query before the server, records only the two completion paths, and refuses a chat completion for more than one choice (`n`).
The server stops with the run, before grading, and with the runner if the runner dies.

### Recorded facts

Before the run launches its workload, `run-input.json` holds the server facts the run verified, so a recovered record carries the same `run_metadata.model_server` and `native_telemetry`.
`run_metadata.model_server.host` records the host's side of the server, which is not part of the candidate (grilling 2026-11-16):

| Field | Holds |
| --- | --- |
| `gpu_slot` | the claimed GPU Slot's value, or null without `gpu_slots` |
| `cuda_visible_devices`, `cuda_device_order` | the server's effective values, each null when absent; without `gpu_slots` they are the runner's, so the record keeps the selection even when `nvidia-smi` cannot be read |
| `gpus` | from `nvidia-smi` at claim, the GPU Slot's GPUs, or without `gpu_slots` every GPU it lists, which `cuda_visible_devices` narrows: `index`, `uuid`, `name`, `memory_total_mib`, `memory_used_mib`, `power_limit_w`, `driver_version` |
| `binary_sha256` | the llama-server binary's digest, recorded and never checked |
| `environment` | the host config's `environment` for the server, empty when it sets none |

When `nvidia-smi` is missing or fails, `gpus` is null with `gpus_reason` (`nvidia_smi_unavailable`, `nvidia_smi_failed` or `nvidia_smi_unreadable`), only the lock decides whether a GPU Slot is free, and the run goes ahead.
`run_metadata.model_server` also keeps the recipe's declaration as written, with `files`, `environment` and the timeouts only when the recipe sets them, so a recipe written before them records what it always did.
A recipe with `files` adds `file_paths` and `file_bytes` for every file, and `model_sha256_verified` covers every declared file; a changed file other than the model fails the run with `model_file_digest_mismatch:<file>` before the server starts (#271).
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
A response with status 200 is complete only when it carries a final choice (`finish_reason`, or a Messages response's `stop_reason`) and, for a stream, ends with `data: [DONE]` (a Messages stream with `message_stop`); one the server ends early is failed with `upstream_response_incomplete`, or `upstream_response_truncated` when a fixed-length body is cut short.
A complete response that reports no usage still counts, with usage partial (`response_usage_missing`).
A request that failed, was cancelled or was unfinished, or a response that reported usage more than once, leaves usage partial (`relayed_request_incomplete`, `multiple_usage_reports`).
Usage follows OpenAI's convention, input including cached tokens; cache writes are zero, and reasoning tokens are missing, because llama.cpp counts them inside completion tokens.
A Messages response reports input apart from cache reads and writes, as Anthropic does; the relay adds them back, the convention every Claude run's usage follows, and takes the output count from the stream's final `message_delta`.
A Messages response carries no `timings`, so a Claude Code run's `server_timings` counts no requests.
No price applies, whatever name the recipe serves the model under: requests are priced from an empty table (`price_table.models` is empty), so the Estimated Cost is unavailable with `model_price_unavailable`; with no Reported Cost either, the Run Cost is that missing estimate, never zero, and `cost_verification` is null (ADR-023).
`measurements.server_timings` sums the server's prompt and generation tokens and times into tokens per second, `coverage.failed_requests` counts requests the relay could not complete, and `coverage.unfinished_requests` those of them that never settled.
A request may set sampling parameters of its own, which llama.cpp honours over the server's flags; each event keeps every key beyond those that only shape the request as `request_parameters` (for a Messages request, Claude Code's `thinking` among them), and `coverage.requests_with_parameter_overrides` counts such requests.
`run_metadata.model_server` records the spec, the binary and its version, the verified digest, and how long verification and start-up took.
The run directory also keeps `model-transcript.jsonl`: per request, the messages added since the last reply and the assembled response, with its reasoning and tool calls.
A Messages request carries its system prompt beside its messages, so a row whose request has no assistant turn yet, the first and each after a compaction, also keeps it as `system`.
A transcript row that cannot be written leaves its request's record unchanged; `coverage.transcript_rows_missing` counts such rows.
What the relay keeps of workload-controlled content is bounded: 1 MiB of messages and of response per request, and a few KiB for each other field, cut with `truncated_from_chars`.

### The Anthropic engine

A recipe may declare `SILVERQUILLM_MODEL_SERVER = '{"engine":"anthropic"}'`, with `request_timeout_seconds` as its only optional key, to run its agent against Anthropic's own API through the same relay (#289). This is how a pi construct runs a Claude model: the agent is pointed at `http://model-server:8080`, as for a local server, with a placeholder key.

- **No server and no GPU Slot.** No llama-server starts and no GPU Slot is claimed.
- **Relay slots (#291).** A host keeps at most `[model_server] anthropic_concurrency` such runs live, 5 when the host config does not set it (1 to 64). It is the host's setting, since it changes no run's result, so it is part of no candidate.
  - Each run claims the first free relay slot, a lock file `<state_root>/anthropic-relay-<i>.lock`, before anything else, and holds it until its relay stops, before grading.
  - With every slot held the run is refused (`anthropic_relay_busy`) and the scheduler defers the entry in its own relay pool, in queue order, until a slot frees, judging from the kernel's lock table as it does for GPU Slots.
  - Relay runs never count as the host's one run without a login or a GPU Slot.
- **What the relay passes on.** The relay passes on only `POST /v1/messages` and `POST /v1/messages/count_tokens`, to `https://api.anthropic.com`, and refuses every other path.
- **Keys (#291).** `<state_root>/api-keys/anthropic` is either one key file, the key `default`, or a directory of key files, each named by 1 to 64 characters, `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; other names, dot files among them, are ignored. The name is recorded, so it is bounded like the other identifiers a record holds. Relay slot *i* uses the *i*-th key in name order modulo their number, so a host with keys from several organizations spreads its runs across their rate limits. An empty directory refuses the run (`model_relay_api_key_unavailable`).
- **The key.** The relay adds the run's API key as `x-api-key`. Each key file must be a regular file of the runner's user that no one else can read, holding one key of at most 256 characters (`[A-Za-z0-9_-]`) and at most one trailing newline. The file is opened without following a link and without blocking, so a link, a FIFO or a device is refused at once, and it is read whole: a longer file, or one holding a second line, is refused rather than read by its prefix. A run is refused before any evidence exists when the file is missing or a link (`model_relay_api_key_unavailable`), not a private regular file (`model_relay_api_key_permissions`), or not one key (`model_relay_api_key_invalid`). A replacement key takes effect from the next run. The key is read once at the start of the run, and the workload never holds it.
- **Headers.** The sidecar and the relay pass on `anthropic-version` and `anthropic-beta` as the workload sent them, with values limited to `[A-Za-z0-9._,-]`. Every other header stops at the sidecar, the workload's own `x-api-key` among them. Without a version the relay sends `2023-06-01`.
- **What is recorded.** The run is recorded like a local one, with the same events, transcript and measurements.
  - `run_metadata.model_server` holds `engine`, `upstream`, `served_model` and `host`: `api_key: "host_secret"`, `api_key_name` (the key's file name, or `default`) and `relay_slot`. It never holds the key, and has no model digest to verify.
  - Each response event adds `upstream: "anthropic"` and the `anthropic_beta` flags it carried.
  - Requests are priced from the standard price table, not the empty one a local server's alias gets.
  - Usage counts cache writes into input, as for every Claude run. Their one-hour share is kept as `cache_write_1h_input_tokens` when `cache_creation` splits the writes consistently, which pricing needs. A request whose writes are not split that way keeps the share unknown and is unpriced (`cache_write_split_missing_or_invalid`).

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-022](../adr/ADR-022-pi-constructs-run-against-a-bench-started-local-model-server.md) | pi constructs run against a bench-started llama.cpp server, observed by a host-side relay |
| [ADR-023](../adr/ADR-023-run-cost-is-the-reported-cost-checked-per-request.md) | A local-model run has no Reported Cost and no price, so its Run Cost stays missing |
