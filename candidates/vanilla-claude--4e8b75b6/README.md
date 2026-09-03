# vanilla-claude

The Claude Code reference candidate (#65): TheOzolith's stock Claude run image
with the vanilla `claude` adapter, no setup instructions, no knowledge tree,
no Agent Policy, and the default model spelled as its most-pinned provider ID.
It **varies nothing** — the fixed point every operator can run and compare
against. A different model, effort, base, or knowledge tree is a different
candidate (export another; see `candidates/README.md`).

## Identity

Recomputed from `bundle/` by TheOzolith's verifier on every run and every
test run — never trusted from this file or the directory name.

| | |
| --- | --- |
| Candidate hash | `4e8b75b69a8a0a4c686bc4cf401aa1ff686f88f18e9e3c8b86a0a1d25a48239d` (hash8 `4e8b75b6`) |
| Adapter | `claude` |
| Base image | `ghcr.io/snowfoxbuilds/theozolith-run-claude:sha-3c0a5df9609a6c9e1f517bd28a2083d11480c31d` |
| Base digest | `sha256:a162d1d32dfc43b0f238b19dc063defc0934beabec8dc8685eb231c64e62ddd1` |
| Instruction hash | `bd5b272bc8ca355b1c2cf25b7d6ad63b123bec7e9391ad2c2606ce140ce7ee7b` |
| Model / effort | `claude-sonnet-5` / the model's default |
| Deterministic image tag | `theozolith/vanilla-claude:sha-3c0a5df9609a6c9e1f517bd28a2083d11480c31d-bd5b272bc8ca` |
| Secret slots (names only) | `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` — bind either |
| Exported | `2026-09-03T03:20:04Z` by theozolith-control 0.3.0 @ `19118cae` (bundle_format_version 2, identity_spec_version 2) |

## Provenance

- **Definition**: `source/worker-types/vanilla-claude.toml`. Re-exporting it
  with the recorded `exported_at` reproduces `bundle/` byte for byte
  (`tests/test_reference_candidates.py` proves it):
  `theozolith candidate export --source candidates/vanilla-claude--4e8b75b6/source --type vanilla-claude --out <dir>`.
- **Base digest**: the digest the-ozolith's publish job pushed for tag
  `sha-3c0a5df9…` (CI run 33655436545, `publish-run-image (claude)` push
  receipt). The image is private on ghcr.io, so resolving it yourself needs a
  `DOCKER_CONFIG` carrying a `read:packages` credential (`docker login ghcr.io`);
  the source pins the digest so export needs no registry access.
- **Model**: `claude-sonnet-5` — the ID TheOzolith's own reference implementer
  definition pins; the current generation ships no dated variant, and family
  aliases (`sonnet`, `opus`, `fable`) are floating names the adapter refuses
  to bake (#39: most-pinned provider ID).
- **driver / secrets** are not identity-bearing (BENCH-CONTRACT.md). The
  driver is `builtin:implementer` so the derived image is exactly what a
  deployed implementer runs (managed-scope model bake).

## Run

```bash
silverquillm run --candidate candidates/vanilla-claude--4e8b75b6 --benchmark smoke --timeout 3600
```
