# Candidates

Current benchmark candidates are explicit Karn Construct Definitions.
Run a definition JSON file directly or promote it into the curated layout:

```sh
python scripts/promote_candidate.py definition.json --slug example
silverquillm run --candidate definition.json --benchmark smoke --mode basic
```

A curated directory contains `bundle/definition.json`, `source/definition.json`, a hashed `source.json` inventory and a README.
Its name ends in the first eight characters of the recomputed definition/image Candidate Hash.
Promotion checks source equality and credential shapes before an atomic rename; publication repeats those checks.
The source copy proves the selected definition, not the build of the immutable image.

The image must already be available in the selected local Docker Engine.
No Ozolith installation, Config Repo, image rebuild or Node receipt is required.
The current host supports launch-private Automatons and explicitly refuses optional capabilities it cannot provide.
See [Bench Contract](../docs/specs/BENCH-CONTRACT.md) and [Benchmark Candidates](../docs/specs/BENCHMARK-CANDIDATES.md).

## Historical references

`vanilla-claude--4e8b75b6` and `vanilla-codex--90a33424` retain their original bundle bytes and historical `ozolith-v1` identities.
They remain evidence for old results and are not accepted as new standalone definitions.
New native references use their own explicit definitions, immutable image pins and source inventories.
Offline CLI and file-interface qualification does not claim model inference or subscription-login qualification.

## Current native references

| Reference | Native CLI | Configured model |
| --- | --- | --- |
| [Claude](vanilla-claude-standalone--650023f7/README.md) | Claude Code 2.1.260 | claude-opus-4-8 |
| [Codex](vanilla-codex-standalone--552e2ed2/README.md) | Codex 0.153.4 | gpt-6-astra |

Build or import the exact selected image into the local Engine before running the definition.
[Reference recipes](../reference-recipes/README.md) explain image production and the offline qualification boundary.
