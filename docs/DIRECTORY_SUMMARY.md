# Directory Summary — `docs/`

## Purpose

Documentation and specification files for the SilverquiLLM-bench project. Contains design specs synced from Notion via `sync_notion_specs.py`.

## Key Files

| Path | Responsibility |
|------|---------------|
| `specs/PROJECT-OVERVIEW.md` | High-level project description and goals |
| `specs/GAME-ENGINE.md` | Game engine architecture and rules coverage spec |
| `specs/CARD-INTERFACE.md` | Card implementation interface and hook method spec |
| `specs/BENCHMARK-RUNNER.md` | Benchmark runner design for LLM evaluation |
| `specs/SCORING.md` | Scoring criteria and evaluation methodology |
| `specs/TEST-SUITE.md` | Test suite design and coverage requirements |

## Dependencies

- Specs are synced from Notion using the root-level `sync_notion_specs.py` script.
- Specs inform the design of `engine/` and `cards/` modules but are not imported by code.

## Notes

- These are reference documents, not executable code.
- The specs directory is populated by the `sync_notion_specs.py` tool and may be updated independently of the codebase.
