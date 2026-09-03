# vanilla-codex

The Codex CLI reference candidate (#65): TheOzolith's stock codex run image
with the vanilla `codex` adapter, no setup instructions, no knowledge tree,
no Agent Policy, and the default model spelled as its most-pinned provider ID.
It **varies nothing** — the fixed point every operator can run and compare
against. A different model, base, or knowledge tree is a different candidate
(export another; see `candidates/README.md`).

## Identity

Recomputed from `bundle/` by TheOzolith's verifier on every run and every
test run — never trusted from this file or the directory name.

| | |
| --- | --- |
| Candidate hash | `90a334246107c853780a5140a9e9fbb565afbd168f6499797f188231e1d0e09c` (hash8 `90a33424`) |
| Adapter | `codex` |
| Base image | `ghcr.io/snowfoxbuilds/theozolith-run-codex:sha-3c0a5df9609a6c9e1f517bd28a2083d11480c31d` |
| Base digest | `sha256:8071882367362695ecc44919b748835f53d7d2e637c37213ab35ab43d5958162` |
| Instruction hash | `dd959a6bf1060457a6166d318536d1776bb473aa323506e6d7c66204205452f7` |
| Model / effort | `gpt-5.2-codex` / none (no codex effort is provably enforceable yet — the-ozolith#88, spike #76) |
| Deterministic image tag | `theozolith/vanilla-codex:sha-3c0a5df9609a6c9e1f517bd28a2083d11480c31d-dd959a6bf106` |
| Secret slots (names only) | `OPENAI_API_KEY` |
| Exported | `2026-09-03T03:21:25Z` by theozolith-control 0.3.0 @ `19118cae` (bundle_format_version 2, identity_spec_version 2) |

## Provenance

- **Definition**: `source/worker-types/vanilla-codex.toml`. Re-exporting it
  with the recorded `exported_at` reproduces `bundle/` byte for byte
  (`tests/test_reference_candidates.py` proves it):
  `theozolith candidate export --source candidates/vanilla-codex--90a33424/source --type vanilla-codex --out <dir>`.
- **Base digest**: resolved anonymously from ghcr.io by
  `theozolith candidate export` (the image is public) and equal to the digest
  the-ozolith's publish job pushed for tag `sha-3c0a5df9…` (CI run
  33655436545, `publish-run-image (codex)` push receipt); the source pins it
  so export needs no registry access.
- **Model**: `gpt-5.2-codex` — the ID TheOzolith's own codex reviewer
  definition pins; `-latest` IDs float and the adapter refuses them (#39:
  most-pinned provider ID).
- **driver / secrets** are not identity-bearing (BENCH-CONTRACT.md). The
  driver is `builtin:implementer` so the derived image is exactly what a
  deployed implementer runs (managed-scope model bake).

## Run

```bash
silverquillm run --candidate candidates/vanilla-codex--90a33424 --benchmark smoke --timeout 3600
```
